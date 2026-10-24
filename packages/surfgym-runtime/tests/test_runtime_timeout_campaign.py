"""Scaled, no-network timeout characterizations for campaign 2026-09-06."""

import asyncio
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from surfgym_contracts.task import LLMJudgeEvaluation
from surfgym_runtime.gateway.error import Deadline, RetryableError
from surfgym_runtime.gateway.server import create_app
from surfgym_runtime.gateway.service import Service
from surfgym_runtime.support.config import Config, GatewayConfig, ProcessTimeout, WavepoolConfig
from surfgym_runtime.support.evaluator import Evaluator, Frame
from surfgym_runtime.wavepool.instance.service import PlaywrightBrowserWorker
from surfgym_runtime.wavepool.instance.session import ContextEntry, ContextManager, ContextPhase


def _config(tmp_path: Path) -> Config:
    return Config(
        task_file_path=tmp_path / "tasks.sqlite3", log_path=tmp_path / "gateway.log",
        gateway=GatewayConfig(host="127.0.0.1", port=58000, gateway_workers=2, gateway_in_flight=1,
            agent_request_timeout=0.05, artifact_reward_timeout=40.0, in_flight_timeout=1.0, deadline_margin=0.01),
        wavepool=WavepoolConfig(host="127.0.0.1", master_port=58010, instance_start_port=58020,
            instances=1, contexts_per_instance=1,
            process_timeout=ProcessTimeout(allocate=1, release=1, screenshot=1, observe=1, execute=1, layer_gap=0.5)),
    )


def test_h9_admitted_request_can_be_dispatched_after_its_public_deadline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_semaphore = asyncio.Semaphore
    entered = threading.Event()
    second_queued = threading.Event()
    allow = threading.Event()
    observed: list[float] = []

    class TrackingSemaphore:
        def __init__(self, value: int) -> None:
            self._inner = real_semaphore(value)

        async def acquire(self) -> bool:
            if self._inner.locked():
                second_queued.set()
            return await self._inner.acquire()

        def release(self) -> None:
            self._inner.release()
    class Store:
        def __init__(self, _path: Path) -> None: pass
        def close(self) -> None: pass
    class FakeService:
        def __init__(self, **_kwargs: object) -> None: pass
        def open(self) -> None: pass
        def close(self) -> None: pass
        def handle_request(self, request: object, deadline_at: float) -> object:
            observed.append(deadline_at - time.monotonic())
            if len(observed) == 1:
                entered.set(); allow.wait(1)
            return {"session_id": getattr(request, "session_id"), "task_id": getattr(request, "task_id"), "image": None}
    monkeypatch.setattr("surfgym_runtime.gateway.server.asyncio.Semaphore", TrackingSemaphore)
    monkeypatch.setattr("surfgym_runtime.gateway.server.TaskStore", Store)
    monkeypatch.setattr("surfgym_runtime.gateway.server.Service", FakeService)
    with TestClient(create_app(_config(tmp_path))) as client:
        first = threading.Thread(target=lambda: client.post("/", json={"op":"start","session_id":1,"task_id":"x"}))
        first.start(); assert entered.wait(1)
        second = threading.Thread(target=lambda: client.post("/", json={"op":"start","session_id":2,"task_id":"x"}))
        second.start()
        assert second_queued.wait(timeout=1)
        time.sleep(0.08)
        allow.set()
        first.join(1)
        second.join(1)
    assert not first.is_alive()
    assert not second.is_alive()
    assert len(observed) == 2
    assert observed[1] < 0


def test_h10_service_allocate_repeats_mutation_when_first_reply_is_lost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("surfgym_runtime.gateway.service.jittered_backoff", lambda: iter([0.0]))
    mutations: list[str] = []

    class Transport:
        def allocate(self, **_kwargs: object):
            mutations.append("transport-mutation")
            if len(mutations) == 1:
                raise RetryableError("reply lost after mutation")
            return SimpleNamespace(context_id="ctx", instance_port=5400)

    service = object.__new__(Service)
    service.transport = Transport()
    deadline = lambda context: Deadline(time.monotonic() + 1, context)
    assert service._allocate(deadline, [], [], []) == ("ctx", 5400)
    assert mutations == ["transport-mutation", "transport-mutation"]


def test_h11_infrastructure_error_and_valid_zero_both_return_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    evaluation = LLMJudgeEvaluation(model="dummy", max_frames=2, image_detail="low")
    trace = [
        Frame(step=0, kind="start", image_b64="AA==", media_type="image/png"),
        Frame(step=1, kind="reward", image_b64="AA==", media_type="image/png"),
    ]
    judge = Evaluator(); judge._api_key = "dummy"
    class BrokenClient:
        def __init__(self, **_kwargs: object) -> None: pass
        def __enter__(self): return self
        def __exit__(self, *_args: object) -> None: pass
        def post(self, *_args: object, **_kwargs: object): raise httpx.TimeoutException("fake")
    monkeypatch.setattr("surfgym_runtime.support.evaluator.httpx.Client", BrokenClient)
    infrastructure_zero = judge.llm_judge_eval("x", trace, evaluation, 0.1)
    class Response:
        def raise_for_status(self) -> None: pass
        def json(self): return {"output_text": '{"score": 0}'}
    class ZeroClient(BrokenClient):
        def post(self, *_args: object, **_kwargs: object): return Response()
    monkeypatch.setattr("surfgym_runtime.support.evaluator.httpx.Client", ZeroClient)
    valid_zero = judge.llm_judge_eval("x", trace, evaluation, 0.1)
    class OneResponse(Response):
        def json(self): return {"output_text": '{"score": 1}'}
    class OneClient(BrokenClient):
        def post(self, *_args: object, **_kwargs: object): return OneResponse()
    monkeypatch.setattr("surfgym_runtime.support.evaluator.httpx.Client", OneClient)
    valid_one = judge.llm_judge_eval("x", trace, evaluation, 0.1)
    assert (infrastructure_zero, valid_zero, valid_one) == (0.0, 0.0, 1.0)


def test_h12_slow_reset_hook_retains_context_until_original_release_completes() -> None:
    worker = PlaywrightBrowserWorker(contexts_per_instance=1)
    reset_started = asyncio.Event(); allow_reset = asyncio.Event(); deleted: list[str] = []
    context = SimpleNamespace(operation_lock=asyncio.Lock())
    async def hook(*_args: object, **_kwargs: object) -> None:
        reset_started.set(); await allow_reset.wait()
    async def delete(context_id: str, _context: object) -> None: deleted.append(context_id)
    worker._run_hooks = hook  # type: ignore[method-assign]
    manager = ContextManager(contexts_per_instance=1, vw=100, vh=100)
    manager._contexts["ctx"] = context  # type: ignore[assignment]
    manager._entries["ctx"] = ContextEntry(phase=ContextPhase.ACTIVE, context=context)
    manager._delete_locked = delete  # type: ignore[method-assign]
    worker.ctx_manager = manager
    async def scenario() -> None:
        task = asyncio.create_task(worker.release("ctx", []))
        reset_waiter = asyncio.create_task(reset_started.wait())
        done, _ = await asyncio.wait({task, reset_waiter}, timeout=0.5, return_when=asyncio.FIRST_COMPLETED)
        assert reset_waiter in done
        if task in done:
            await task
        try:
            with pytest.raises(asyncio.TimeoutError): await asyncio.wait_for(asyncio.shield(task), 0.02)
            assert deleted == []
        finally:
            allow_reset.set()
            await task
    asyncio.run(scenario())
    assert deleted == ["ctx"]
