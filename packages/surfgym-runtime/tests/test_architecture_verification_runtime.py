"""Deterministic regressions for runtime lifecycle boundaries."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from surfgym_contracts.computer13 import TypingAction
from surfgym_contracts.protocol.agent_to_gateway import ActionRequest
from surfgym_contracts.protocol.gateway_to_upstream import GatewayAllocateRequest
from surfgym_contracts.task import ConsoleCriteria, CriteriaEvaluation, Hook, Website
from surfgym_runtime.gateway.error import Deadline, RetryableError
from surfgym_runtime.gateway.registry import Lease, SessionRegistry, SessionState
from surfgym_runtime.gateway.service import Service
from surfgym_runtime.gateway import server as gateway_server
from surfgym_runtime.support import Config
from surfgym_runtime.support.config import GatewayConfig, ProcessTimeout, WavepoolConfig
from surfgym_runtime.support import evaluator as evaluator_module
from surfgym_runtime.support.evaluator import Evaluator, Frame
from surfgym_runtime.wavepool.instance.session import ContextManager, ContextPhase
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker
from surfgym_runtime.wavepool.master.registry import LeaseRegistry
from surfgym_runtime.wavepool.master.error import AllocationDispatchedError
from surfgym_runtime.wavepool.master.service import MasterService


def _deadline(context: str) -> Deadline:
    return Deadline(time.monotonic() + 5.0, context)


def _master(client: object) -> tuple[MasterService, LeaseRegistry]:
    registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
    master: Any = object.__new__(MasterService)
    master.config = SimpleNamespace(host="127.0.0.1")
    master.client = client
    master.registry = registry
    master._release_wakeup = asyncio.Event()
    return master, registry


def test_lost_allocate_reply_retains_capacity_until_terminal_release() -> None:
    """A release retry is the only event that returns a lost allocation's slot."""

    @dataclass
    class LostReplyThenLateCreateClient:
        created: set[str] = field(default_factory=set)
        allocate_context_id: str | None = None
        release_completed: bool = False
        live_snapshot_requested: bool = False

        async def allocate(self, _port: int, context_id: str, _request: object) -> None:
            self.allocate_context_id = context_id
            raise RuntimeError("lost allocate reply before late Instance completion")

        async def release(self, _context_id: str, _port: int, _request: object) -> None:
            if not self.release_completed:
                raise RuntimeError("lost release reply")

        async def live_context_ids(self, _port: int) -> set[str]:
            self.live_snapshot_requested = True
            raise AssertionError("capacity reconciliation must not consult a live snapshot")

        def complete_late_instance_work(self) -> None:
            assert self.allocate_context_id is not None
            self.created.add(self.allocate_context_id)

    async def scenario() -> None:
        client = LostReplyThenLateCreateClient()
        master, registry = _master(client)
        with pytest.raises(AllocationDispatchedError) as raised:
            await master.allocate(
                GatewayAllocateRequest(
                    websites=[Website(website_id="fixture", url="http://fixture.test")],
                    hooks=[],
                )
            )
        assert raised.value.status_code == 502
        assert raised.value.retryable is False
        assert raised.value.message == "Instance allocation failed after dispatch"

        await master.release_all()
        client.complete_late_instance_work()
        assert client.created == {client.allocate_context_id}
        assert client.live_snapshot_requested is False
        assert await registry.reserve_lease() is None

        client.release_completed = True
        await master.release_all()
        assert await registry.reserve_lease() is not None

    asyncio.run(scenario())


def test_context_manager_records_creating_entry_and_holds_it_through_new_page_barrier() -> None:
    class Page:
        async def set_viewport_size(self, _viewport: object) -> None:
            return None

        async def add_init_script(self, *, script: str) -> None:
            return None

        async def close(self) -> None:
            return None

    class BrowserContext:
        def __init__(self) -> None:
            self.page_started = asyncio.Event()
            self.allow_page = asyncio.Event()

        async def new_page(self) -> Page:
            self.page_started.set()
            await self.allow_page.wait()
            return Page()

        async def close(self) -> None:
            return None

    class Browser:
        def __init__(self, context: BrowserContext) -> None:
            self.context = context

        async def new_context(self, **_options: object) -> BrowserContext:
            return self.context

    async def scenario() -> None:
        pending_context = BrowserContext()
        manager = ContextManager(contexts_per_instance=1, vw=100, vh=100)
        manager._b = Browser(pending_context)  # type: ignore[assignment]
        creating = asyncio.create_task(
            manager.create("creating", [Website(website_id="web", url="http://fixture.test")])
        )
        await pending_context.page_started.wait()
        assert manager.live_context_ids() == ()
        entry = manager._entries["creating"]
        assert entry.phase is ContextPhase.CREATING
        assert entry.context is None
        assert entry.partial_browser_context is pending_context
        assert len(manager._entries) == manager.contexts_per_instance
        pending_context.allow_page.set()
        await creating
        assert manager.live_context_ids() == ("creating",)

    asyncio.run(scenario())


def test_current_multi_action_execution_is_prefix_only_and_never_automatically_retries() -> None:
    class PrefixFailureTransport:
        def __init__(self) -> None:
            self.executed: list[str] = []
            self.screenshots = 0

        def execute(self, _deadline: Deadline, _context_id: str, _port: int, command: object) -> None:
            text = command.text  # type: ignore[attr-defined]
            self.executed.append(text)
            if text == "second":
                raise RetryableError("lost reply after the second command")

        def screenshot(self, *_args: object, **_kwargs: object) -> object:
            self.screenshots += 1
            raise AssertionError("post-action screenshot must not run after execute failure")

    registry = SessionRegistry()
    registry.start_session(
        7,
        SessionState(task_id="task", lease=Lease(context_id="ctx", port=9000), release_hooks=[]),
    )
    transport = PrefixFailureTransport()
    service: Any = object.__new__(Service)
    service.transport = transport
    service._session_registry = registry
    service.process_timeout = SimpleNamespace(screenshot=1.0)

    with pytest.raises(RetryableError, match="lost reply"):
        service._handle_action(
            ActionRequest(
                op="action",
                session_id=7,
                task_id="task",
                actions=[TypingAction(action_type="TYPING", text="first"), TypingAction(action_type="TYPING", text="second")],
            ),
            _deadline,
        )

    assert transport.executed == ["first", "second"]
    assert transport.screenshots == 0
    assert registry.require_session_state(7, "task").action_history == ["TYPING"]


def test_duplicate_public_action_request_repeats_the_executed_prefix_without_an_operation_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    class PrefixFailureTransport:
        def __init__(self) -> None:
            self.executed: list[str] = []

        def execute(self, _deadline: Deadline, _context_id: str, _port: int, command: object) -> None:
            text = command.text  # type: ignore[attr-defined]
            self.executed.append(text)
            if text == "second":
                raise RetryableError("lost reply after the second command")

    registry = SessionRegistry()
    registry.start_session(
        8,
        SessionState(task_id="task", lease=Lease(context_id="ctx", port=9000), release_hooks=[]),
    )
    transport = PrefixFailureTransport()
    service: Any = object.__new__(Service)
    service.transport = transport
    service._session_registry = registry
    service.process_timeout = SimpleNamespace(screenshot=1.0)
    service.open = lambda: None
    service.close = lambda: None
    service._screenshot = lambda _deadline, _lease: ("image", "image/png")
    request = ActionRequest(
        op="action",
        session_id=8,
        task_id="task",
        actions=[TypingAction(action_type="TYPING", text="first"), TypingAction(action_type="TYPING", text="second")],
    )

    class Store:
        def __init__(self, _path: object) -> None:
            return None

        def close(self) -> None:
            return None

    config = Config(
        task_file_path=tmp_path / "tasks.sqlite3",
        log_path=tmp_path / "gateway.log",
        gateway=GatewayConfig(
            host="127.0.0.1",
            port=18000,
            gateway_workers=1,
            gateway_in_flight=1,
            agent_request_timeout=5.0,
            artifact_reward_timeout=40.0,
            in_flight_timeout=5.0,
            deadline_margin=0.1,
        ),
        wavepool=WavepoolConfig(
            host="127.0.0.1",
            master_port=5500,
            instance_start_port=9000,
            instances=1,
            contexts_per_instance=1,
            process_timeout=ProcessTimeout(
                allocate=1.0,
                release=1.0,
                screenshot=1.0,
                observe=1.0,
                execute=1.0,
                layer_gap=0.0,
            ),
        ),
    )
    monkeypatch.setattr(gateway_server, "TaskStore", Store)
    monkeypatch.setattr(gateway_server, "Service", lambda **_kwargs: service)
    app = gateway_server.create_app(config)
    payload = request.model_dump(mode="json")
    control = {
        "op": "action",
        "session_id": 8,
        "task_id": "task",
        "actions": [{"action_type": "TYPING", "text": "control"}],
    }
    with TestClient(app) as client:
        control_response = client.post("/", json=control)
        first = client.post("/", json=payload)
        duplicate = client.post("/", json=payload)

    assert control_response.json()["status"] == "ok"
    assert first.json()["status"] == "error"
    assert duplicate.json()["status"] == "error"
    assert transport.executed == ["control", "first", "second", "first", "second"]
    assert registry.require_session_state(8, "task").action_history == ["TYPING", "TYPING", "TYPING"]


def test_llm_judge_freezes_frame_input_before_the_source_trace_is_mutated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frames = [
        Frame(step=0, kind="start", image_b64="first", media_type="image/png"),
        Frame(step=1, kind="reward", image_b64="reward", media_type="image/png"),
    ]
    evaluation = SimpleNamespace(model="model", image_detail="low", max_frames=2)
    recorded: dict[str, object] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"output_text": '{"score": 1.0}'}

    class Client:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 1.0

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, _url: str, *, headers: object, json: dict[str, object]) -> Response:
            recorded.update(json)
            frames[:] = [Frame(step=2, kind="reward", image_b64="reset", media_type="image/png")]
            return Response()

    monkeypatch.setattr(evaluator_module.httpx, "Client", Client)
    evaluator = Evaluator()
    evaluator._api_key = "test-key"
    assert evaluator.llm_judge_eval("instruction", frames, evaluation, timeout=1.0) == 1.0

    content = recorded["input"][0]["content"]  # type: ignore[index]
    image_urls = [item["image_url"] for item in content if item["type"] == "input_image"]
    assert image_urls == ["data:image/png;base64,first", "data:image/png;base64,reward"]
    assert frames == [Frame(step=2, kind="reward", image_b64="reset", media_type="image/png")]


def test_trace_buffer_remains_bounded_across_repeated_action_frames_and_keeps_boundary_frames() -> None:
    state = SessionState(task_id="task", lease=Lease(context_id="ctx", port=1), release_hooks=[])
    state.append_frame(kind="start", image_b64="start", media_type="image/png")
    for step in range(80):
        state.append_frame(kind="action", image_b64=str(step), media_type="image/png")
    state.append_frame(kind="reward", image_b64="reward", media_type="image/png")

    assert len(state.trace) == 50
    assert state.trace[0].kind == "start"
    assert state.trace[-1].kind == "reward"


def test_real_browser_observation_remains_evaluable_after_release_reset_and_context_close() -> None:
    """Opt-in loopback proof of capture/evaluation separation, with no LLM or fixture app."""
    if os.environ.get("RUN_ARCHITECTURE_BROWSER") != "1":
        pytest.skip("set RUN_ARCHITECTURE_BROWSER=1 to run the local Playwright regression")

    state = {"value": "before"}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/reset":
                state["value"] = "reset"
                self.send_response(204)
                self.end_headers()
                return
            if self.path != "/":
                self.send_response(404)
                self.end_headers()
                return
            body = f"<html><script>window.fixtureValue={state['value']!r}</script></html>".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://127.0.0.1:{server.server_port}/"
    events: list[tuple[str, float]] = []
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    criterion = ConsoleCriteria(
        website_id="fixture",
        script="() => window.fixtureValue",
        value="before",
    )
    evaluation = CriteriaEvaluation(criteria=[criterion])

    async def scenario() -> None:
        await worker.open()
        try:
            await worker.allocate("first", [Website(website_id="fixture", url=url)], [])
            captured = await worker.observe("first", [criterion], [])
            events.append(("captured", time.monotonic()))
            assert Evaluator().rule_based_eval(evaluation, captured) == 1.0

            await worker.release(
                "first",
                [Hook(website_id="fixture", timing="before", script="fetch('/reset')")],
            )
            events.append(("released", time.monotonic()))
            assert worker.ctx_manager.live_context_ids() == ()

            await worker.allocate("second", [Website(website_id="fixture", url=url)], [])
            fresh = await worker.observe("second", [criterion], [])
            events.append(("fresh", time.monotonic()))
            assert fresh == ["reset"]
            assert Evaluator().rule_based_eval(evaluation, fresh) == 0.0

            await worker.release("second", [])
            events.append(("closed", time.monotonic()))
            assert worker.ctx_manager.live_context_ids() == ()
            assert Evaluator().rule_based_eval(evaluation, captured) == 1.0
        finally:
            await worker.close()

    try:
        asyncio.run(scenario())
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)

    assert [name for name, _timestamp in events] == ["captured", "released", "fresh", "closed"]
    assert all(later >= earlier for (_, earlier), (_, later) in zip(events, events[1:]))
