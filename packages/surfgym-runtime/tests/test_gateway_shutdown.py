import time
from concurrent.futures import ThreadPoolExecutor as RealThreadPoolExecutor
from pathlib import Path
from queue import SimpleQueue
from threading import Event, Lock, Thread
from typing import Any

import pytest
from fastapi.testclient import TestClient
from surfgym_contracts.protocol.agent_to_gateway import RewardRequest
from surfgym_contracts.protocol.gateway_to_agent import RewardResponse
from surfgym_runtime.gateway.registry import Lease, SessionState
from surfgym_runtime.gateway.server import create_app
from surfgym_runtime.gateway.worker import ReleaseJob, ReleaseWorker
from surfgym_runtime.support import Config
from surfgym_runtime.support.config import GatewayConfig, ProcessTimeout, WavepoolConfig


def _config(tmp_path: Path) -> Config:
    return Config(
        task_file_path=tmp_path / "tasks.sqlite3",
        log_path=tmp_path / "gateway.log",
        gateway=GatewayConfig(
            host="127.0.0.1",
            port=58000,
            gateway_workers=2,
            gateway_in_flight=2,
            verl_timeout=5.0,
            artifact_reward_timeout=40.0,
            in_flight_timeout=1.0,
            deadline_margin=0.1,
        ),
        wavepool=WavepoolConfig(
            host="127.0.0.1",
            master_port=58010,
            instance_start_port=58020,
            instances=1,
            contexts_per_instance=1,
            process_timeout=ProcessTimeout(
                allocate=1.0,
                release=1.0,
                screenshot=1.0,
                observe=1.0,
                execute=1.0,
                layer_gap=0.5,
            ),
        ),
    )


def test_server_selects_artifact_budget_from_typed_reward_request_and_drains_executor_first(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    events: list[str] = []
    remaining: list[tuple[bool, float]] = []

    class RecordingExecutor(RealThreadPoolExecutor):
        def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
            events.append(f"executor:{wait}:{cancel_futures}")
            super().shutdown(wait=wait, cancel_futures=cancel_futures)

    class Store:
        def __init__(self, _path: Path) -> None:
            pass

        def close(self) -> None:
            events.append("store")

    class GatewayService:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def open(self) -> None:
            events.append("service-open")

        def close(self) -> None:
            events.append("service-close")

        def handle_request(self, request: RewardRequest, deadline_at: float) -> RewardResponse:
            remaining.append((request.artifacts is not None, deadline_at - time.monotonic()))
            return RewardResponse(
                session_id=request.session_id,
                task_id=request.task_id,
                reward=1.0,
            )

    monkeypatch.setattr("surfgym_runtime.gateway.server.ThreadPoolExecutor", RecordingExecutor)
    monkeypatch.setattr("surfgym_runtime.gateway.server.TaskStore", Store)
    monkeypatch.setattr("surfgym_runtime.gateway.server.Service", GatewayService)

    with TestClient(create_app(_config(tmp_path))) as client:
        legacy = client.post(
            "/",
            json={"op": "reward", "session_id": 1, "task_id": "task-id"},
        )
        artifact = client.post(
            "/",
            json={
                "op": "reward",
                "session_id": 2,
                "task_id": "task-id",
                "artifacts": [{"path": "Desktop/out.txt", "max_bytes": 32}],
            },
        )
        assert legacy.status_code == 200
        assert artifact.status_code == 200

    assert remaining[0][0] is False
    assert 4.0 < remaining[0][1] <= 4.9
    assert remaining[1][0] is True
    assert 39.0 < remaining[1][1] <= 39.9
    assert events[-3:] == ["executor:True:False", "service-close", "store"]


def test_release_worker_close_waits_for_fifo_drain_with_bounded_attempts() -> None:
    first_entered = Event()
    unblock_first = Event()
    calls: list[tuple[str, float]] = []

    class Transport:
        def release(self, *, deadline: Any, context_id: str, **_kwargs: object) -> None:
            calls.append((context_id, deadline.remaining()))
            if context_id == "first":
                first_entered.set()
                unblock_first.wait(timeout=3)

    worker = ReleaseWorker(transport=Transport(), release_timeout=0.25)
    worker.start()
    worker.enqueue(
        SessionState(
            task_id="task-id",
            lease=Lease(context_id="first", port=3000),
            release_hooks=[],
        )
    )
    worker.enqueue(
        SessionState(
            task_id="task-id",
            lease=Lease(context_id="second", port=3001),
            release_hooks=[],
        )
    )
    assert first_entered.wait(timeout=2)

    closed = Event()

    def close() -> None:
        worker.close()
        closed.set()

    closer = Thread(target=close)
    closer.start()
    assert not closed.wait(timeout=1.1)
    unblock_first.set()
    closer.join(timeout=2)

    assert closed.is_set()
    assert [context_id for context_id, _remaining in calls] == ["first", "second"]
    assert all(0 < remaining <= 0.25 for _context_id, remaining in calls)


class _ObservedLifecycleLock:
    def __init__(self) -> None:
        self._lock = Lock()
        self.contended_acquire = Event()

    def __enter__(self) -> "_ObservedLifecycleLock":
        if self._lock.locked():
            self.contended_acquire.set()
        self._lock.acquire()
        return self

    def __exit__(self, *_args: object) -> None:
        self._lock.release()


class _GatedRetryQueue:
    def __init__(self) -> None:
        self._queue: SimpleQueue[ReleaseJob | None] = SimpleQueue()
        self.retry_put_entered = Event()
        self.allow_retry_put = Event()
        self.items: list[ReleaseJob | None] = []

    def put(self, item: ReleaseJob | None) -> None:
        if item is not None:
            self.retry_put_entered.set()
            self.allow_retry_put.wait(timeout=2)
        self.items.append(item)
        self._queue.put(item)

    def get(self) -> ReleaseJob | None:
        return self._queue.get()


class _RecordingQueue:
    def __init__(self) -> None:
        self.items: list[ReleaseJob | None] = []

    def put(self, item: ReleaseJob | None) -> None:
        self.items.append(item)


def _release_job(context_id: str = "retry") -> ReleaseJob:
    return ReleaseJob(
        context_id=context_id,
        port=3000,
        release_hooks=[],
        attempts=1,
    )


def _session_state(context_id: str = "late") -> SessionState:
    return SessionState(
        task_id="task-id",
        lease=Lease(context_id=context_id, port=3000),
        release_hooks=[],
    )


def test_release_retry_that_entered_before_close_is_queued_before_sentinel() -> None:
    worker = ReleaseWorker(transport=object(), release_timeout=0.25)
    lifecycle_lock = _ObservedLifecycleLock()
    queue = _GatedRetryQueue()
    worker._lifecycle_lock = lifecycle_lock
    worker._queue = queue
    retry_job = _release_job()

    retry = Thread(target=worker._requeue, args=(retry_job,))
    retry.start()
    assert queue.retry_put_entered.wait(timeout=2)

    closer = Thread(target=worker.close)
    closer.start()
    close_waited_on_retry = lifecycle_lock.contended_acquire.wait(timeout=1)
    queue.allow_retry_put.set()
    retry.join(timeout=2)
    closer.join(timeout=2)

    assert close_waited_on_retry is True
    assert not retry.is_alive()
    assert not closer.is_alive()
    assert queue.items == [retry_job, None]


def test_release_worker_rejects_enqueue_and_drops_retry_after_idempotent_close() -> None:
    worker = ReleaseWorker(transport=object(), release_timeout=0.25)
    queue = _RecordingQueue()
    worker._queue = queue

    worker.close()
    with pytest.raises(RuntimeError, match="closed"):
        worker.enqueue(_session_state())
    worker._requeue(_release_job())
    worker.close()

    assert queue.items == [None]
