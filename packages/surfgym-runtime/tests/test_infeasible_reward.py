import base64
import hashlib
import time
from collections.abc import Callable
from threading import Barrier, Event, Thread
from types import SimpleNamespace
from typing import Any

import pytest
from surfgym_contracts.protocol.agent_to_gateway import RewardRequest
from surfgym_contracts.protocol.artifact import ArtifactPayload, ArtifactSpec
from surfgym_contracts.protocol.gateway_to_agent import RewardBundleResponse, RewardResponse
from surfgym_contracts.task import (
    CriteriaEvaluation,
    DomCriteria,
    Evaluation,
    InfeasibleEvaluation,
    LLMJudgeEvaluation,
    Observation,
    Task,
    Website,
)
from surfgym_runtime.gateway.error import Deadline, InvalidRequest, RetryableError
from surfgym_runtime.gateway.registry import Lease, SessionRegistry, SessionState
from surfgym_runtime.gateway.service import Service
from surfgym_runtime.support import Frame


class RecordingEvaluator:
    def __init__(self):
        self.rule_based_calls = 0
        self.llm_calls = 0

    def rule_based_eval(
        self, evaluation: CriteriaEvaluation, observations: list[Observation]
    ) -> float:
        self.rule_based_calls += 1
        return 0.4

    def llm_judge_eval(
        self,
        instruction: str,
        trace: list[Frame],
        evaluation: LLMJudgeEvaluation,
        timeout: float,
    ) -> float:
        self.llm_calls += 1
        return 0.6


class RecordingReleaseWorker:
    def __init__(self):
        self.enqueued: list[SessionState] = []

    def enqueue(self, state: SessionState) -> None:
        self.enqueued.append(state)


class SingleTaskStore:
    def __init__(self, task: Task):
        self.task = task

    def get(self, task_id: str) -> Task | None:
        return self.task if task_id == self.task.task_id else None


def _task(evaluation: Evaluation) -> Task:
    return Task(
        task_id="task-id",
        instruction="Complete the task.",
        website=[Website(url="http://example.test")],
        evaluation=evaluation,
    )


def _session(*history: str) -> SessionState:
    state = SessionState(
        task_id="task-id",
        lease=Lease(context_id="context-id", port=3000),
        release_hooks=[],
    )
    state.action_history.extend(history)
    return state


def _deadline(context: str) -> Deadline:
    return Deadline(time.monotonic() + 10.0, context)


def _artifact_payload(path: str) -> ArtifactPayload:
    raw = path.encode()
    return ArtifactPayload(
        path=path,
        mime_type="text/plain",
        sha256=hashlib.sha256(raw).hexdigest(),
        size=len(raw),
        encoding="base64",
        data=base64.b64encode(raw).decode("ascii"),
    )


@pytest.mark.parametrize(
    ("history", "expected_reward"),
    [
        (["FAIL"], 1.0),
        (["DONE"], 0.0),
        (["TYPING"], 0.0),
        ([], 0.0),
    ],
)
def test_infeasible_reward_depends_only_on_last_action(history: list[str], expected_reward: float):
    service: Any = object.__new__(Service)
    evaluator = RecordingEvaluator()
    service.evaluator = evaluator

    reward = service._compute_reward(
        task=_task(InfeasibleEvaluation()),
        session_state=_session(*history),
        deadline=_deadline,
    )

    assert reward == expected_reward
    assert evaluator.rule_based_calls == 0
    assert evaluator.llm_calls == 0


def test_fail_short_circuits_criteria_evaluation():
    service: Any = object.__new__(Service)
    evaluator = RecordingEvaluator()
    observed: list[dict[str, object]] = []

    def observe(**kwargs: object) -> None:
        observed.append(kwargs)

    service.evaluator = evaluator
    service._observe = observe

    reward = service._compute_reward(
        task=_task(CriteriaEvaluation(criteria=[DomCriteria(selector="#result", value="done")])),
        session_state=_session("FAIL"),
        deadline=_deadline,
    )

    assert reward == 0.0
    assert observed == []
    assert evaluator.rule_based_calls == 0


def test_fail_short_circuits_llm_evaluation():
    service: Any = object.__new__(Service)
    evaluator = RecordingEvaluator()
    screenshots: list[tuple[Callable[[str], Deadline], Lease]] = []

    def screenshot(deadline: Callable[[str], Deadline], lease: Lease) -> tuple[str, str]:
        screenshots.append((deadline, lease))
        return ("image", "image/png")

    service.evaluator = evaluator
    service._screenshot = screenshot

    reward = service._compute_reward(
        task=_task(LLMJudgeEvaluation()),
        session_state=_session("FAIL"),
        deadline=_deadline,
    )

    assert reward == 0.0
    assert screenshots == []
    assert evaluator.llm_calls == 0


def test_done_runs_existing_criteria_evaluation():
    service: Any = object.__new__(Service)
    evaluator = RecordingEvaluator()

    def observe(**kwargs: object) -> Any:
        return SimpleNamespace(observation=["done"])

    service.evaluator = evaluator
    service._observe = observe

    reward = service._compute_reward(
        task=_task(CriteriaEvaluation(criteria=[DomCriteria(selector="#result", value="done")])),
        session_state=_session("DONE"),
        deadline=_deadline,
    )

    assert reward == 0.4
    assert evaluator.rule_based_calls == 1


def test_done_runs_existing_llm_evaluation():
    service: Any = object.__new__(Service)
    evaluator = RecordingEvaluator()

    def screenshot(deadline: Callable[[str], Deadline], lease: Lease) -> tuple[str, str]:
        return ("image", "image/png")

    service.evaluator = evaluator
    service._screenshot = screenshot

    reward = service._compute_reward(
        task=_task(LLMJudgeEvaluation()),
        session_state=_session("DONE"),
        deadline=_deadline,
    )

    assert reward == 0.6
    assert evaluator.llm_calls == 1


def test_reward_releases_and_ends_session_for_infeasible_task():
    task = _task(InfeasibleEvaluation())
    service: Any = object.__new__(Service)
    service.task_store = SingleTaskStore(task)
    session_registry = SessionRegistry()
    release_worker = RecordingReleaseWorker()
    service._session_registry = session_registry
    service._release_worker = release_worker
    session = _session("FAIL")
    session_registry.start_session(1, session)
    service.evaluator = RecordingEvaluator()

    response = service._handle_reward(
        RewardRequest(op="reward", task_id="task-id", session_id=1),
        _deadline,
    )

    assert response.reward == 1.0
    assert type(response) is RewardResponse
    assert "artifacts" not in response.model_dump(mode="json")
    assert release_worker.enqueued == [session]
    with pytest.raises(InvalidRequest, match="not active"):
        session_registry.require_session_state(1, "task-id")


def test_reward_failure_still_releases_and_ends_session():
    task = _task(InfeasibleEvaluation())
    service: Any = object.__new__(Service)
    service.task_store = SingleTaskStore(task)
    session_registry = SessionRegistry()
    release_worker = RecordingReleaseWorker()
    service._session_registry = session_registry
    service._release_worker = release_worker
    session = _session("FAIL")
    session_registry.start_session(1, session)

    def fail_reward(**kwargs: object) -> float:
        raise RuntimeError("reward failed")

    service._compute_reward = fail_reward

    with pytest.raises(RuntimeError, match="reward failed"):
        service._handle_reward(
            RewardRequest(op="reward", task_id="task-id", session_id=1),
            _deadline,
        )

    assert release_worker.enqueued == [session]
    with pytest.raises(InvalidRequest, match="not active"):
        session_registry.require_session_state(1, "task-id")


def test_artifact_reward_returns_artifacts_in_declared_order_after_reward() -> None:
    service: Any = object.__new__(Service)
    service.task_store = SingleTaskStore(_task(InfeasibleEvaluation()))
    service._session_registry = SessionRegistry()
    service._release_worker = RecordingReleaseWorker()
    session = _session("FAIL")
    service._session_registry.start_session(1, session)
    events: list[str] = []

    def compute_reward(**_kwargs: object) -> float:
        events.append("reward")
        return 1.0

    def artifact(**kwargs: object) -> ArtifactPayload:
        spec = kwargs["artifact"]
        assert isinstance(spec, ArtifactSpec)
        events.append(spec.path)
        return _artifact_payload(spec.path)

    service._compute_reward = compute_reward
    service._artifact = artifact
    request = RewardRequest(
        op="reward",
        task_id="task-id",
        session_id=1,
        artifacts=[
            ArtifactSpec(path="Desktop/first.txt", max_bytes=32),
            ArtifactSpec(path="Desktop/second.txt", max_bytes=32),
        ],
    )

    response = service._handle_reward(request, _deadline)

    assert type(response) is RewardBundleResponse
    assert [item.path for item in response.artifacts] == [
        "Desktop/first.txt",
        "Desktop/second.txt",
    ]
    assert events == ["reward", "Desktop/first.txt", "Desktop/second.txt"]
    assert service._release_worker.enqueued == [session]


@pytest.mark.parametrize("failure_stage", ["compute", "image", "first", "later"])
def test_every_reward_failure_enqueues_and_ends_exactly_once(failure_stage: str) -> None:
    task = _task(InfeasibleEvaluation())
    if failure_stage == "image":
        task = task.model_copy(update={"include_reward_image": True})
    service: Any = object.__new__(Service)
    service.task_store = SingleTaskStore(task)
    service._session_registry = SessionRegistry()
    service._release_worker = RecordingReleaseWorker()
    session = _session("FAIL")
    service._session_registry.start_session(1, session)
    artifact_calls = 0

    def compute_reward(**_kwargs: object) -> float:
        if failure_stage == "compute":
            raise RuntimeError("stage failed")
        return 1.0

    def screenshot(*_args: object, **_kwargs: object) -> tuple[str, str]:
        raise RuntimeError("stage failed")

    def artifact(**kwargs: object) -> ArtifactPayload:
        nonlocal artifact_calls
        artifact_calls += 1
        if failure_stage == "first" or (failure_stage == "later" and artifact_calls == 2):
            raise RuntimeError("stage failed")
        spec = kwargs["artifact"]
        return _artifact_payload(spec.path)

    service._compute_reward = compute_reward
    service._screenshot = screenshot
    service._artifact = artifact

    with pytest.raises(RuntimeError, match="stage failed"):
        service._handle_reward(
            RewardRequest(
                op="reward",
                task_id="task-id",
                session_id=1,
                artifacts=[
                    ArtifactSpec(path="Desktop/first.txt", max_bytes=32),
                    ArtifactSpec(path="Desktop/second.txt", max_bytes=32),
                ],
            ),
            _deadline,
        )

    assert service._release_worker.enqueued == [session]
    with pytest.raises(InvalidRequest, match="not active"):
        service._session_registry.require_session_state(1, "task-id")


def test_duplicate_concurrent_rewards_compute_artifact_and_enqueue_once() -> None:
    service: Any = object.__new__(Service)
    service.task_store = SingleTaskStore(_task(InfeasibleEvaluation()))
    service._session_registry = SessionRegistry()
    service._release_worker = RecordingReleaseWorker()
    session = _session("FAIL")
    service._session_registry.start_session(1, session)
    entered = Barrier(2)
    release_compute = Event()
    compute_calls = 0
    artifact_calls = 0
    results: list[object] = []

    def compute_reward(**_kwargs: object) -> float:
        nonlocal compute_calls
        compute_calls += 1
        entered.wait(timeout=2)
        release_compute.wait(timeout=2)
        return 1.0

    def artifact(**kwargs: object) -> ArtifactPayload:
        nonlocal artifact_calls
        artifact_calls += 1
        return _artifact_payload(kwargs["artifact"].path)

    service._compute_reward = compute_reward
    service._artifact = artifact
    request = RewardRequest(
        op="reward",
        task_id="task-id",
        session_id=1,
        artifacts=[ArtifactSpec(path="Desktop/out.txt", max_bytes=32)],
    )

    def call_reward() -> None:
        try:
            results.append(service._handle_reward(request, _deadline))
        except Exception as exc:
            results.append(exc)

    first = Thread(target=call_reward)
    first.start()
    entered.wait(timeout=2)
    second = Thread(target=call_reward)
    second.start()
    release_compute.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert compute_calls == 1
    assert artifact_calls == 1
    assert service._release_worker.enqueued == [session]
    assert sum(type(result) is RewardBundleResponse for result in results) == 1
    assert sum(isinstance(result, InvalidRequest) for result in results) == 1


def test_artifact_list_uses_one_shared_deadline_and_raw_bounded_timeouts() -> None:
    service: Any = object.__new__(Service)
    service.task_store = SingleTaskStore(_task(InfeasibleEvaluation()))
    service._session_registry = SessionRegistry()
    service._release_worker = RecordingReleaseWorker()
    service._session_registry.start_session(1, _session("FAIL"))
    service._compute_reward = lambda **_kwargs: 1.0
    service.process_timeout = SimpleNamespace(layer_gap=0.5)
    deadline_contexts: list[str] = []
    timeout_caps: list[float] = []
    returned_timeouts = iter([35.5, 20.0])
    transport_deadlines: list[float] = []

    class SharedDeadline:
        def remaining(self) -> float:
            return 40.0

        def timeout_for(self, maximum: float) -> float:
            timeout_caps.append(maximum)
            return next(returned_timeouts)

    shared = SharedDeadline()

    def deadline(context: str) -> SharedDeadline:
        deadline_contexts.append(context)
        return shared

    class Transport:
        def artifact(self, *, artifact: ArtifactSpec, timeout: float, **_kwargs: object):
            transport_deadlines.append(timeout)
            return _artifact_payload(artifact.path)

    service.transport = Transport()
    response = service._handle_reward(
        RewardRequest(
            op="reward",
            task_id="task-id",
            session_id=1,
            artifacts=[
                ArtifactSpec(path="Desktop/first.txt", max_bytes=32),
                ArtifactSpec(path="Desktop/second.txt", max_bytes=32),
            ],
        ),
        deadline,
    )

    assert type(response) is RewardBundleResponse
    assert deadline_contexts == ["reward", "artifact"]
    assert timeout_caps == [35.5, 35.5]
    assert transport_deadlines == [35.5, 20.0]


def test_artifact_retryable_failure_is_not_retried() -> None:
    service: Any = object.__new__(Service)
    service.task_store = SingleTaskStore(_task(InfeasibleEvaluation()))
    service._session_registry = SessionRegistry()
    service._release_worker = RecordingReleaseWorker()
    session = _session("FAIL")
    service._session_registry.start_session(1, session)
    service._compute_reward = lambda **_kwargs: 1.0
    service.process_timeout = SimpleNamespace(layer_gap=0.0)
    calls = 0

    class Transport:
        def artifact(self, **_kwargs: object):
            nonlocal calls
            calls += 1
            raise RetryableError("artifact unavailable")

    service.transport = Transport()
    with pytest.raises(RetryableError, match="artifact unavailable"):
        service._handle_reward(
            RewardRequest(
                op="reward",
                task_id="task-id",
                session_id=1,
                artifacts=[ArtifactSpec(path="Desktop/out.txt", max_bytes=32)],
            ),
            _deadline,
        )

    assert calls == 1
    assert service._release_worker.enqueued == [session]
