from typing import Any

import pytest
from surfgym_contracts.protocol.agent_to_gateway import StartRequest
from surfgym_contracts.task import InfeasibleEvaluation, Task, Website
from surfgym_runtime.gateway.error import Deadline
from surfgym_runtime.gateway.registry import SessionRegistry
from surfgym_runtime.gateway.service import Service
from surfgym_runtime.gateway.worker import ReleaseJob, ReleaseWorker


def _deadline(_context: str) -> Deadline:
    return Deadline(float("inf"), "test")


def _task() -> Task:
    return Task(
        task_id="task-id",
        instruction="task",
        website=[Website(website_id="web", url="http://fixture.test")],
        evaluation=InfeasibleEvaluation(),
    )


def test_start_allocate_failure_enqueues_predispatch_uuid_release_descriptor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Store:
        def get(self, task_id: str) -> Task | None:
            return _task() if task_id == "task-id" else None

    class Worker:
        def __init__(self) -> None:
            self.jobs: list[ReleaseJob] = []

        def enqueue(self, job: ReleaseJob) -> None:
            self.jobs.append(job)

    service: Any = object.__new__(Service)
    service.task_store = Store()
    service._session_registry = SessionRegistry()
    service._release_worker = Worker()
    allocated_ids: list[str] = []

    def lose_allocate(*args: object, **_kwargs: object) -> tuple[str, int]:
        allocated_ids.append(args[-1])
        raise RuntimeError("response lost")

    service._allocate = lose_allocate
    expected_uuid = "5e9408dc-75b7-4a54-9b94-e9ebb2749f1e"
    monkeypatch.setattr("surfgym_runtime.gateway.service.uuid.uuid4", lambda: expected_uuid)

    with pytest.raises(RuntimeError, match="response lost"):
        service._handle_start(StartRequest(op="start", session_id=1, task_id="task-id"), _deadline)

    assert service._release_worker.jobs == [
        ReleaseJob(context_id=expected_uuid, port=None, release_hooks=())
    ]
    assert allocated_ids == [expected_uuid]
    assert 1 not in service._session_registry.session_states


def test_release_worker_deduplicates_context_and_retains_unknown_failure() -> None:
    class Queue:
        def __init__(self) -> None:
            self.items: list[ReleaseJob | None] = []

        def put(self, item: ReleaseJob | None) -> None:
            self.items.append(item)

    worker = ReleaseWorker(transport=object(), release_timeout=1.0)
    queue = Queue()
    worker._queue = queue
    job = ReleaseJob(context_id="context", port=None, release_hooks=[])

    worker.enqueue(job)
    worker.enqueue(job)
    assert queue.items == [job]

    retries: list[ReleaseJob] = []
    worker._schedule_retry = lambda retry_job, _error: retries.append(retry_job)
    worker._transport = type("Transport", (), {
        "release": lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("lost response"))
    })()
    worker._handle_job(job)

    assert retries == [job]
    assert "context" in worker._pending_context_ids


def test_release_job_snapshots_hooks_before_later_mutation() -> None:
    from surfgym_contracts.task import Hook
    from surfgym_runtime.gateway.registry import Lease, SessionState

    hooks = [Hook(timing="before", script="release()")]
    state = SessionState(task_id="task", lease=Lease("context", 1), release_hooks=hooks)
    job = ReleaseJob.from_session(state)
    hooks.clear()

    assert len(job.release_hooks) == 1
