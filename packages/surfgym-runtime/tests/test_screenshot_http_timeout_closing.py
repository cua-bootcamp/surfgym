from __future__ import annotations

import asyncio
import base64
import socket
from concurrent.futures import Future
from contextlib import suppress
from threading import Event, Thread
from time import monotonic, sleep
from typing import Any

import httpx
import pytest
import uvicorn
from surfgym_contracts.protocol.gateway_to_upstream import GatewayReleaseRequest
from surfgym_runtime.wavepool.instance.server import create_app
from surfgym_runtime.wavepool.instance.service import NativeBinding, PlaywrightBrowserWorker
from surfgym_runtime.wavepool.instance.session import Context, ContextManager, ContextPhase
from surfgym_runtime.wavepool.master.registry import LeaseRegistry
from surfgym_runtime.wavepool.master.service import MasterService


_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class _BrowserContext:
    def __init__(self) -> None:
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1


class _BlockingPage:
    def __init__(self, entered: Event, allow: Event, loop: list[asyncio.AbstractEventLoop]):
        self.entered = entered
        self.allow = allow
        self.loop = loop

    async def screenshot(self) -> bytes:
        self.loop[:] = [asyncio.get_running_loop()]
        self.entered.set()
        while not self.allow.is_set():
            await asyncio.sleep(0.01)
        return _PNG

    async def close(self) -> None:
        return None


def _free_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return int(candidate.getsockname()[1])


def _wait_for_health(port: int) -> None:
    deadline = monotonic() + 3
    while monotonic() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.1).status_code == 200:
                return
        except httpx.HTTPError:
            sleep(0.02)
    raise AssertionError("instance HTTP server did not become ready")


def _master(registry: LeaseRegistry, client: object) -> MasterService:
    master = object.__new__(MasterService)
    master.registry = registry
    master.client = client
    master._release_wakeup = asyncio.Event()
    master._release_tasks = {}
    master._release_semaphore = asyncio.Semaphore(1)
    return master


def test_http_screenshot_timeout_fences_master_capacity_until_native_cleanup_completes(
    monkeypatch: Any,
) -> None:
    """An HTTP screenshot timeout cannot make the Master slot reusable early.

    The endpoint and client timeout are real HTTP. Browser/page and native
    cleanup are controlled component doubles, so the CLOSING interval is
    deterministic; this is not Docker or headed-browser evidence.
    """
    entered, allow_screenshot = Event(), Event()
    cleanup_started, allow_cleanup = Event(), Event()
    server_loop: list[asyncio.AbstractEventLoop] = []
    manager = ContextManager(contexts_per_instance=1, vw=100, vh=100)
    browser_context = _BrowserContext()
    page = _BlockingPage(entered, allow_screenshot, server_loop)
    context = Context(
        "ctx", browser_context, {"native": (page, None)}, "native", ("native",)
    )  # type: ignore[arg-type]
    manager._contexts["ctx"] = context
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    worker.ctx_manager = manager
    binding = NativeBinding(
        "ctx", "native", "http://native.test", None, None, "cleanup-capability"
    )
    worker._native_bindings["ctx"] = binding
    cleanup_calls: list[str] = []

    async def cleanup(owned_binding: NativeBinding, **_kwargs: object) -> None:
        cleanup_calls.append(owned_binding.context_id)
        cleanup_started.set()
        while not allow_cleanup.is_set():
            await asyncio.sleep(0.01)

    worker._release_native_binding = cleanup  # type: ignore[method-assign]
    monkeypatch.setattr(
        "surfgym_runtime.wavepool.instance.server.PlaywrightBrowserWorker", lambda **_kwargs: worker
    )
    monkeypatch.setattr(worker, "open", lambda: asyncio.sleep(0))
    monkeypatch.setattr(worker, "close", lambda: asyncio.sleep(0))

    port = _free_port()
    app = create_app(contexts_per_instance=1)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = Thread(target=lambda: server.run(), daemon=True)
    thread.start()
    _wait_for_health(port)
    master_release: Future[object] | None = None
    try:
        with pytest.raises(httpx.TimeoutException):
            httpx.post(
                f"http://127.0.0.1:{port}/screenshot?context_id=ctx",
                json={},
                timeout=0.05,
            )
        assert entered.wait(timeout=1)
        active_before_release = manager._entries["ctx"].active_operation_task
        assert active_before_release is not None
        assert not active_before_release.done()
        assert manager._entries["ctx"].phase is ContextPhase.ACTIVE
        assert context.operation_lock.locked()

        class Client:
            def __init__(self) -> None:
                self.release_calls: list[str] = []

            async def release(
                self,
                context_id: str,
                _port: int,
                request: GatewayReleaseRequest,
            ) -> None:
                self.release_calls.append(context_id)
                release = asyncio.run_coroutine_threadsafe(
                    worker.release(context_id, request.hooks), server_loop[0]
                )
                await asyncio.wrap_future(release)

        async def exercise_master_capacity() -> None:
            registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
            lease = await registry.reserve_lease("ctx")
            assert lease is not None
            await registry.enqueue_release(lease.context_id, GatewayReleaseRequest(hooks=[]))
            client = Client()
            master = _master(registry, client)
            releasing = asyncio.create_task(master.release_all())
            try:
                await asyncio.wait_for(asyncio.to_thread(cleanup_started.wait, 1), timeout=1.2)
                entry = manager._entries["ctx"]
                assert entry.phase is ContextPhase.CLOSING
                assert entry.context is None
                assert browser_context.close_calls == 1
                assert entry.active_operation_task is None
                assert active_before_release.done()
                assert not context.operation_lock.locked()
                assert worker._native_bindings["ctx"] is binding
                assert [pending.context_id for pending in await registry.pending_releases()] == ["ctx"]
                assert await registry.reserve_lease("blocked") is None
                assert client.release_calls == ["ctx"]
                assert cleanup_calls == ["ctx"]

                allow_cleanup.set()
                await asyncio.wait_for(releasing, timeout=2)
            finally:
                allow_cleanup.set()
                if not releasing.done():
                    await asyncio.wait_for(releasing, timeout=2)

            assert await registry.pending_releases() == []
            assert manager._entries["ctx"].phase is ContextPhase.CLOSED
            assert "ctx" not in manager._contexts
            assert "ctx" not in worker._native_bindings
            successor = await registry.reserve_lease("successor")
            assert successor is not None and successor.port_slot.port == lease.port_slot.port
            assert await registry.reserve_lease("second-successor") is None

        master_release = asyncio.run_coroutine_threadsafe(exercise_master_capacity(), server_loop[0])
        master_release.result(timeout=4)
    finally:
        allow_screenshot.set()
        allow_cleanup.set()
        if master_release is not None and not master_release.done():
            with suppress(Exception):
                master_release.result(timeout=2)
        server.should_exit = True
        thread.join(timeout=3)
        assert not thread.is_alive()
