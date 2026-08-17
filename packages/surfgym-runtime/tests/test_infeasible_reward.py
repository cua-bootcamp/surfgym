import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from surfgym_contracts.protocol.agent_to_gateway import RewardRequest
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
from surfgym_runtime.gateway.error import Deadline, InvalidRequest
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


@pytest.mark.parametrize(
    ("history", "expected_reward"),
    [
        (["FAIL"], 1.0),
        (["DONE"], 0.0),
        (["TYPING"], 0.0),
        ([], 0.0),
    ],
)
def test_infeasible_reward_depends_only_on_last_action(
    history: list[str], expected_reward: float
):
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

    def screenshot(
        deadline: Callable[[str], Deadline], lease: Lease
    ) -> tuple[str, str]:
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

    def screenshot(
        deadline: Callable[[str], Deadline], lease: Lease
    ) -> tuple[str, str]:
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
