from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio
import requests
import uvicorn
from surfgym_runtime.gateway.server import create_app as create_gateway_app
from surfgym_runtime.support import (
    GatewayConfig,
    ProcessTimeout,
    TaskStore,
    WavepoolConfig,
    deploy_logger,
    gateway_logger,
    instance_logger,
    master_logger,
)
from surfgym_runtime.wavepool.master.server import create_app as create_master_app

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

STATIC_PAGE_TITLE = "Test Page"
STATIC_PAGE_HTML = f"""<!doctype html>
<html>
<head><title>{STATIC_PAGE_TITLE}</title></head>
<body><h1>Surfgym test fixture page</h1></body>
</html>
""".encode("utf-8")

DEFAULT_PROCESS_TIMEOUT = {
    "allocate": 60.0,
    "release": 30.0,
    "screenshot": 30.0,
    "observe": 30.0,
    "execute": 15.0,
    "layer_gap": 1.0,
}


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# `_serve_in_background` passes `log_config=None` to uvicorn.Config so it
# doesn't clobber this process's own logging setup. That also means
# uvicorn's own access-log line (e.g. `POST / HTTP/1.1 200 OK`) has no
# handler and is silently dropped. Attach one so in-process servers
# (master/gateway) still print it, same as subprocess-hosted ones do via
# ManagedProcess's stdout streaming.
_uvicorn_access_logger = logging.getLogger("uvicorn.access")
if not _uvicorn_access_logger.handlers:
    _uvicorn_access_logger.addHandler(logging.StreamHandler())
    _uvicorn_access_logger.setLevel(logging.INFO)


def patch_gateway_transport_logging():
    """Context manager that logs gateway's *outgoing* requests/responses to
    master/instance (`[gateway→upstream]`/`[gateway←upstream]`).

    Only meaningful when gateway runs in-process (see
    `master_and_gateway_stack`) -- `unittest.mock.patch` can't reach into a
    real subprocess's memory. gateway/transport.py uses the synchronous
    `requests` library (not httpx), which has no `event_hooks` mechanism, so
    this patches `requests.request` itself rather than setting a hook.
    """
    original_request = requests.request

    def logged_request(method, url, **kwargs):
        print(f"[gateway→upstream] {method} {url}")
        response = original_request(method, url, **kwargs)
        print(f"[gateway←upstream] {response.status_code} {response.text[:200]}")
        return response

    return patch(
        "surfgym_runtime.gateway.transport.requests.request", side_effect=logged_request
    )


_COMPONENT_LOGGERS = [gateway_logger, master_logger, instance_logger, deploy_logger]


@pytest.fixture(autouse=True)
def _reset_component_loggers():
    """gateway_logger/master_logger/instance_logger/deploy_logger are module-
    level singletons (created once at import time). `setup_logging()` is a
    no-op once a logger already has handlers, so if a server is ever hosted
    *in-process* (as opposed to subprocess, where each server gets its own
    fresh interpreter/module state), a handler attached by one test would
    silently keep pointing at that test's own tmp_path in every later test
    within the same pytest session. Clearing handlers before each test lets
    `setup_logging()` attach fresh ones pointing at the current test's paths.

    Harmless no-op for purely subprocess-based tests (those never call
    `setup_logging()` in this process at all).
    """
    for logger in _COMPONENT_LOGGERS:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
    yield
    for logger in _COMPONENT_LOGGERS:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)


class _StaticPageHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(STATIC_PAGE_HTML)))
        self.end_headers()
        self.wfile.write(STATIC_PAGE_HTML)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture(scope="session")
def static_site_url():
    """A tiny local HTTP server serving a fixed page with a known <title>.

    Used as the task's `website` URL so tests don't depend on real internet
    sites and can assert on a deterministic DOM criteria (page title).
    """
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), _StaticPageHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _is_healthy(client: httpx.Client, url: str) -> bool:
    try:
        response = client.get(url)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def _wait_for_health(urls: list[str], *, timeout: float, processes: list["ManagedProcess"]) -> None:
    deadline = time.monotonic() + timeout
    with httpx.Client(timeout=2.0) as client:
        while time.monotonic() < deadline:
            for proc in processes:
                proc.assert_alive()
            if all(_is_healthy(client, url) for url in urls):
                return
            time.sleep(0.5)

    raise TimeoutError(f"Servers not healthy after {timeout}s: {urls}")


class ManagedProcess:
    def __init__(self, name: str, cmd: list[str], log_file: Path) -> None:
        self.name = name
        self.log_file = log_file
        self._log_fh = open(log_file, "w", encoding="utf-8", errors="replace")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        # This repo's source reads some files (e.g. _page_script.js) via
        # bare open() without an explicit encoding. On a non-UTF-8 system
        # locale (e.g. Windows w/ Korean codepage cp949) that fails to
        # decode UTF-8 content. PYTHONUTF8 forces Python's default text
        # encoding to UTF-8 for the *subprocess only* -- a test-environment
        # setting, not a source change.
        env["PYTHONUTF8"] = "1"

        self.process = subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )

        # A dedicated reader thread keeps the pipe drained (an unread PIPE
        # fills its OS buffer and hangs the child process) *and* echoes each
        # line to this test process's own stdout, so `pytest -s` shows
        # gateway/master/instance logs live in the terminal, not just in the
        # log file.
        self._reader_thread = threading.Thread(
            target=self._stream_output, name=f"stream-{name}", daemon=True
        )
        self._reader_thread.start()

    def _stream_output(self) -> None:
        stdout = self.process.stdout
        if stdout is None:
            return

        try:
            for line in stdout:
                self._log_fh.write(line)
                self._log_fh.flush()
                print(f"[{self.name}] {line}", end="")
        finally:
            stdout.close()

    def assert_alive(self) -> None:
        code = self.process.poll()
        if code is not None:
            self._log_fh.flush()
            output = self.log_file.read_text(encoding="utf-8", errors="replace")
            raise RuntimeError(f"{self.name} exited early with code {code}\n{output}")

    def tail_log(self) -> str:
        self._log_fh.flush()
        return self.log_file.read_text(encoding="utf-8", errors="replace")

    def stop(self, timeout: float = 5.0) -> None:
        if self.process.poll() is None:
            # Note: on Windows, terminate() hard-kills the process, so
            # uvicorn's ASGI lifespan shutdown (and Playwright's
            # browser.close()) never runs. Any Chromium child process
            # spawned by an instance server may be left behind. Acceptable
            # for this first pass; revisit if orphaned browser processes
            # become a problem in CI.
            self.process.terminate()
        self._stop_after_terminate(timeout)

    def _stop_after_terminate(self, timeout: float) -> None:
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=timeout)
        finally:
            # Let the reader thread drain remaining output (it exits on its
            # own once the pipe hits EOF after the process dies) before we
            # close the file out from under it.
            self._reader_thread.join(timeout=2.0)
            self._log_fh.close()


def _build_config(
    tmp_path: Path,
    *,
    task_rows: list[dict],
    instances: int,
    contexts_per_instance: int,
    process_timeout: dict | None = None,
    gateway_overrides: dict | None = None,
) -> tuple[Path, dict]:
    task_file = tmp_path / "tasks.jsonl"
    task_file.write_text(
        "\n".join(json.dumps(row) for row in task_rows) + "\n",
        encoding="utf-8",
    )

    log_path = tmp_path / "logs"

    gateway_config = {
        "host": "127.0.0.1",
        "port": _free_port(),
        "gateway_workers": 4,
        "gateway_in_flight": 4,
        "verl_timeout": 120.0,
        "in_flight_timeout": 60.0,
        "deadline_margin": 3.0,
    }
    gateway_config.update(gateway_overrides or {})

    config = {
        "task_file_path": str(task_file),
        "log_path": str(log_path),
        "gateway": gateway_config,
        "wavepool": {
            "host": "127.0.0.1",
            "master_port": _free_port(),
            "instance_start_port": _free_port(),
            "instances": instances,
            "contexts_per_instance": contexts_per_instance,
            "process_timeout": process_timeout or DEFAULT_PROCESS_TIMEOUT,
        },
    }

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    return config_path, config


@pytest.fixture
def wavepool_stack(tmp_path: Path):
    """Spins up gateway + master + instance(s) as real subprocesses.

    Usage:
        gateway_url = wavepool_stack(
            task_rows=[...], instances=1, contexts_per_instance=1,
        )

    No source code is modified or injected into for testing purposes; every
    server is launched exactly the way `scripts/*_launch.bash` launches it in
    production (`python -m surfgym_runtime.<...>.server/launch <config>`).
    """
    processes: list[ManagedProcess] = []

    def start(
        *,
        task_rows: list[dict],
        instances: int = 1,
        contexts_per_instance: int = 1,
        process_timeout: dict | None = None,
        startup_timeout: float = 60.0,
    ) -> str:
        config_path, config = _build_config(
            tmp_path,
            task_rows=task_rows,
            instances=instances,
            contexts_per_instance=contexts_per_instance,
            process_timeout=process_timeout,
        )

        wavepool = config["wavepool"]
        gateway = config["gateway"]
        proc_log_dir = tmp_path / "proc_logs"
        proc_log_dir.mkdir(parents=True, exist_ok=True)

        processes.append(
            ManagedProcess(
                "master",
                [PYTHON, "-m", "surfgym_runtime.wavepool.master.server", str(config_path)],
                proc_log_dir / "master.log",
            )
        )

        for i in range(instances):
            port = wavepool["instance_start_port"] + i
            processes.append(
                ManagedProcess(
                    f"instance:{port}",
                    [
                        PYTHON,
                        "-m",
                        "surfgym_runtime.wavepool.instance.server",
                        "--host",
                        wavepool["host"],
                        "--port",
                        str(port),
                        "--log-path",
                        config["log_path"],
                        "--contexts-per-instance",
                        str(contexts_per_instance),
                    ],
                    proc_log_dir / f"instance_{port}.log",
                )
            )

        processes.append(
            ManagedProcess(
                "gateway",
                [PYTHON, "-m", "surfgym_runtime.gateway.launch", str(config_path)],
                proc_log_dir / "gateway.log",
            )
        )

        health_urls = [
            f"http://{wavepool['host']}:{wavepool['master_port']}/health",
            f"http://{gateway['host']}:{gateway['port']}/health",
            *(
                f"http://{wavepool['host']}:{wavepool['instance_start_port'] + i}/health"
                for i in range(instances)
            ),
        ]
        _wait_for_health(health_urls, timeout=startup_timeout, processes=processes)

        return f"http://{gateway['host']}:{gateway['port']}/"

    try:
        yield start
    finally:
        for proc in reversed(processes):
            proc.stop()


@pytest.fixture
def real_instance(tmp_path: Path):
    """Spins up a single real `instance` server subprocess (Playwright), with
    no gateway/master involved. Meant for white-box tests that drive
    `MasterService`/`LeaseRegistry` directly, in this same test process, so
    internal registry state (`_lease`, `_pending_releases`) can be asserted
    on directly -- something impossible against a real master subprocess,
    since a subprocess is a separate memory space `patch`/introspection
    cannot reach into.
    """
    processes: list[ManagedProcess] = []
    proc_log_dir = tmp_path / "proc_logs"
    proc_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = tmp_path / "logs"

    def start(*, contexts_per_instance: int = 1, startup_timeout: float = 60.0) -> tuple[str, int]:
        host = "127.0.0.1"
        port = _free_port()

        processes.append(
            ManagedProcess(
                f"instance:{port}",
                [
                    PYTHON,
                    "-m",
                    "surfgym_runtime.wavepool.instance.server",
                    "--host",
                    host,
                    "--port",
                    str(port),
                    "--log-path",
                    str(log_path),
                    "--contexts-per-instance",
                    str(contexts_per_instance),
                ],
                proc_log_dir / f"instance_{port}.log",
            )
        )

        _wait_for_health(
            [f"http://{host}:{port}/health"], timeout=startup_timeout, processes=processes
        )
        return host, port

    try:
        yield start
    finally:
        for proc in reversed(processes):
            proc.stop()


def _route_endpoint(app, path: str):
    for route in app.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise LookupError(f"No route for path={path!r} on {app}")


def _closure_var(func, name: str):
    """Recover a variable captured in `func`'s enclosing scope, without
    touching source. `master/server.py`'s `create_app()` builds `master`
    (a `MasterService`) as a local variable and only returns the FastAPI
    `app` -- but a Python closure keeps a live reference to it in the route
    handler's `__closure__`, which `co_freevars` lets us look up by name.
    `@wraps` (used by `handle_master_errors`) sets `__wrapped__` to the
    pre-decoration function automatically.
    """
    target = getattr(func, "__wrapped__", func)
    freevars = target.__code__.co_freevars
    if name not in freevars:
        raise AttributeError(
            f"{name!r} not found in closure of "
            f"{getattr(target, '__qualname__', target)}: {freevars}"
        )
    return target.__closure__[freevars.index(name)].cell_contents


async def _serve_in_background(
    app, host: str, port: int, servers: list[uvicorn.Server], tasks: list[asyncio.Task]
) -> None:
    server = uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, lifespan="on", log_config=None)
    )
    servers.append(server)
    tasks.append(asyncio.create_task(server.serve()))

    deadline = time.monotonic() + 15.0
    while not server.started and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    if not server.started:
        raise TimeoutError(f"in-process uvicorn server on port {port} did not start in time")


@pytest_asyncio.fixture
async def master_and_gateway_stack(real_instance):
    """gateway AND master both hosted as real `uvicorn.Server`s in-process
    (asyncio tasks on this test's own event loop); a real `instance` still
    runs as a subprocess (real Playwright).

    An earlier attempt ran all three servers in-process (including
    instance/Playwright) and crashed with a Windows segfault. A follow-up
    experiment kept instance as a subprocess and hosted only gateway+master
    in-process (2 uvicorn.Servers, no Playwright in this process) and passed
    repeatedly -- consistent with Playwright-in-the-same-loop being the
    actual crash trigger, not merely "multiple servers". This fixture uses
    that smaller, validated combination.

    Because gateway and master both run in this process, both are
    recoverable via closure reflection (see `_closure_var`) and inspectable
    directly: `gateway_service._session_registry.session_states`,
    `gateway_service._release_worker._queue`, `master_service.registry`, etc.
    Real HTTP/networking to gateway is unchanged -- the test still talks to
    it over a real socket, exactly like a real client would.

    Usage:
        stack = await master_and_gateway_stack(task_rows=[...])
        stack["gateway_url"]      # http://127.0.0.1:PORT/
        stack["master_service"]   # MasterService (registry._lease, etc.)
        stack["gateway_service"]  # Service (_session_registry, etc.)
    """
    servers: list[uvicorn.Server] = []
    tasks: list[asyncio.Task] = []

    async def start(
        *,
        task_rows: list[dict],
        contexts_per_instance: int = 1,
        process_timeout: dict | None = None,
        gateway_overrides: dict | None = None,
    ) -> dict:
        host = "127.0.0.1"
        _, instance_port = real_instance(contexts_per_instance=contexts_per_instance)

        wavepool_config = WavepoolConfig(
            host=host,
            master_port=_free_port(),
            instance_start_port=instance_port,
            instances=1,
            contexts_per_instance=contexts_per_instance,
            process_timeout=ProcessTimeout(**(process_timeout or DEFAULT_PROCESS_TIMEOUT)),
        )

        master_app = create_master_app(wavepool_config)
        master_service = _closure_var(_route_endpoint(master_app, "/allocate"), "master")
        await _serve_in_background(master_app, host, wavepool_config.master_port, servers, tasks)

        gateway_kwargs = {
            "host": host,
            "port": _free_port(),
            "gateway_workers": 4,
            "gateway_in_flight": 4,
            "verl_timeout": 120.0,
            "in_flight_timeout": 60.0,
            "deadline_margin": 3.0,
        }
        gateway_kwargs.update(gateway_overrides or {})
        gateway_config = GatewayConfig(**gateway_kwargs)
        task_store = TaskStore.from_rows(task_rows)

        gateway_app = create_gateway_app(
            gateway_config=gateway_config,
            wavepool_config=wavepool_config,
            task_store=task_store,
        )
        gateway_route_wrapper = _route_endpoint(gateway_app, "/")
        raw_handle_request = _closure_var(gateway_route_wrapper, "func")
        gateway_service = _closure_var(raw_handle_request, "service")
        await _serve_in_background(gateway_app, host, gateway_config.port, servers, tasks)

        return {
            "gateway_url": f"http://{host}:{gateway_config.port}/",
            "master_service": master_service,
            "gateway_service": gateway_service,
        }

    try:
        yield start
    finally:
        for server in servers:
            server.should_exit = True
        for task in tasks:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(task, timeout=5.0)


def make_task_row(
    *,
    task_id: str,
    website_url: str,
    title: str,
    complexity: int = 1,
    allocate_hooks: list[dict] | None = None,
) -> dict:
    """A minimal, self-contained Task row: rule-based criteria checking the
    fixture page's <title>, so the test needs no LLM/API key to grade reward.

    `allocate_hooks` (optional): raw Hook dicts for `lifecycle_hooks.allocate`
    (e.g. `[{"timing": "before", "mode": "api", "method": "GET", "url": ...}]`),
    for tests that need a before/after allocate hook to fail deliberately.
    Omitted entirely (not even an empty list) unless passed, so existing
    callers' task rows are byte-for-byte unchanged.
    """
    row: dict = {
        "task_id": task_id,
        "instruction": f"Confirm the fixture page titled '{title}' loaded.",
        "website": [{"url": website_url}],
        "hash": f"test-hash-{task_id}",
        "evaluation": {
            "criteria": [
                {"target": "title", "match": "exact", "value": title},
            ],
        },
        "complexity": complexity,
    }
    if allocate_hooks:
        row["lifecycle_hooks"] = {"allocate": allocate_hooks}
    return row
