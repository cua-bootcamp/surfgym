from collections.abc import Callable
from threading import Event, Thread
from typing import Any

import pytest
from surfgym_contracts.command import Command
from surfgym_contracts.computer13 import Computer13, DoneAction, FailAction, TypingAction
from surfgym_contracts.protocol.agent_to_gateway import ActionRequest, RewardRequest
from surfgym_contracts.task import InfeasibleEvaluation, Task, Website
from surfgym_runtime.gateway.error import Deadline, InvalidRequest
from surfgym_runtime.gateway.registry import Lease, SessionRegistry, SessionState
from surfgym_runtime.gateway.service import Service


def _deadline(context: str) -> Deadline:
    return Deadline(float("inf"), context)


def _service_with_session() -> tuple[Any, SessionState, list[Command]]:
    service: Any = object.__new__(Service)
    service._session_registry = SessionRegistry()
    executed: list[Command] = []

    def execute(deadline: Callable[[str], Deadline], lease: Lease, command: Command) -> None:
        executed.append(command)

    def screenshot(deadline: Callable[[str], Deadline], lease: Lease) -> tuple[str, str]:
        return ("image", "image/png")

    service._execute = execute
    service._screenshot = screenshot

    session = SessionState(
        task_id="task-id",
        lease=Lease(context_id="context-id", port=3000),
        release_hooks=[],
    )
    service._session_registry.start_session(1, session)
    return service, session, executed


def _request(*actions: Computer13) -> ActionRequest:
    return ActionRequest(
        op="action",
        session_id=1,
        task_id="task-id",
        actions=list(actions),
    )


def test_terminal_action_is_recorded_without_instance_command():
    service, session, executed = _service_with_session()

    service._handle_action(
        _request(FailAction(action_type="FAIL")),
        _deadline,
    )

    assert session.action_history == ["FAIL"]
    assert executed == []


@pytest.mark.parametrize(
    "actions",
    [
        [FailAction(action_type="FAIL"), TypingAction(action_type="TYPING", text="x")],
        [DoneAction(action_type="DONE"), FailAction(action_type="FAIL")],
    ],
)
def test_terminal_action_must_be_the_only_action_in_its_request(
    actions: list[Computer13],
):
    service, session, executed = _service_with_session()

    with pytest.raises(InvalidRequest, match="Terminal action"):
        service._handle_action(_request(*actions), _deadline)

    assert session.action_history == []
    assert executed == []


def test_action_request_after_terminal_action_is_rejected():
    service, session, executed = _service_with_session()
    service._handle_action(
        _request(DoneAction(action_type="DONE")),
        _deadline,
    )

    with pytest.raises(InvalidRequest, match="terminal"):
        service._handle_action(
            _request(TypingAction(action_type="TYPING", text="x")),
            _deadline,
        )

    assert session.action_history == ["DONE"]
    assert executed == []


def test_nonterminal_action_is_executed_and_recorded():
    service, session, executed = _service_with_session()

    service._handle_action(
        _request(TypingAction(action_type="TYPING", text="x")),
        _deadline,
    )

    assert session.action_history == ["TYPING"]
    assert len(executed) == 1


def test_failed_nonterminal_action_is_not_recorded():
    service, session, executed = _service_with_session()

    def fail_execute(deadline: Callable[[str], Deadline], lease: Lease, command: Command) -> None:
        raise RuntimeError("execute failed")

    service._execute = fail_execute

    with pytest.raises(RuntimeError, match="execute failed"):
        service._handle_action(
            _request(TypingAction(action_type="TYPING", text="x")),
            _deadline,
        )

    assert session.action_history == []
    assert executed == []


def test_concurrent_action_requests_are_serialized() -> None:
    service, session, executed = _service_with_session()
    first_entered = Event()
    release_first = Event()
    results: list[object] = []

    def execute(deadline: Callable[[str], Deadline], lease: Lease, command: Command) -> None:
        executed.append(command)
        if len(executed) == 1:
            first_entered.set()
            release_first.wait(timeout=2)

    service._execute = execute

    def call(request: ActionRequest) -> None:
        try:
            results.append(service._handle_action(request, _deadline))
        except Exception as exc:
            results.append(exc)

    first = Thread(
        target=call,
        args=(_request(TypingAction(action_type="TYPING", text="first")),),
    )
    second = Thread(
        target=call,
        args=(_request(TypingAction(action_type="TYPING", text="second")),),
    )
    first.start()
    assert first_entered.wait(timeout=2)
    second.start()

    assert len(executed) == 1
    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not any(isinstance(result, Exception) for result in results)
    assert session.action_history == ["TYPING", "TYPING"]
    assert len(executed) == 2


class _TaskStore:
    def __init__(self) -> None:
        self.task = Task(
            task_id="task-id",
            instruction="task",
            website=[Website(url="http://example.test")],
            evaluation=InfeasibleEvaluation(),
        )

    def get(self, task_id: str) -> Task | None:
        return self.task if task_id == self.task.task_id else None


class _ReleaseWorker:
    def __init__(self) -> None:
        self.enqueued: list[SessionState] = []

    def enqueue(self, state: SessionState) -> None:
        self.enqueued.append(state)


def test_reward_claim_blocks_later_action_and_cleans_up_once() -> None:
    service, session, _executed = _service_with_session()
    service.task_store = _TaskStore()
    service._release_worker = _ReleaseWorker()
    reward_entered = Event()
    release_reward = Event()
    action_results: list[object] = []

    def compute_reward(**_kwargs: object) -> float:
        reward_entered.set()
        release_reward.wait(timeout=2)
        return 1.0

    service._compute_reward = compute_reward

    reward_thread = Thread(
        target=lambda: service._handle_reward(
            RewardRequest(op="reward", session_id=1, task_id="task-id"), _deadline
        )
    )
    reward_thread.start()
    assert reward_entered.wait(timeout=2)

    def call_action() -> None:
        try:
            action_results.append(
                service._handle_action(
                    _request(TypingAction(action_type="TYPING", text="late")), _deadline
                )
            )
        except Exception as exc:
            action_results.append(exc)

    action_thread = Thread(target=call_action)
    action_thread.start()
    assert action_results == []
    release_reward.set()
    reward_thread.join(timeout=2)
    action_thread.join(timeout=2)

    assert len(service._release_worker.enqueued) == 1
    assert service._release_worker.enqueued == [session]
    assert len(action_results) == 1
    assert isinstance(action_results[0], InvalidRequest)
    assert session.action_history == []


def test_action_first_finishes_before_reward_claim() -> None:
    service, session, _executed = _service_with_session()
    service.task_store = _TaskStore()
    service._release_worker = _ReleaseWorker()
    action_entered = Event()
    release_action = Event()
    reward_entered = Event()
    results: list[object] = []

    def execute(*_args: object, **_kwargs: object) -> None:
        action_entered.set()
        release_action.wait(timeout=2)

    def compute_reward(**_kwargs: object) -> float:
        reward_entered.set()
        return 0.5

    service._execute = execute
    service._compute_reward = compute_reward
    action_thread = Thread(
        target=lambda: results.append(
            service._handle_action(
                _request(TypingAction(action_type="TYPING", text="first")), _deadline
            )
        )
    )
    reward_thread = Thread(
        target=lambda: results.append(
            service._handle_reward(
                RewardRequest(op="reward", session_id=1, task_id="task-id"), _deadline
            )
        )
    )
    action_thread.start()
    assert action_entered.wait(timeout=2)
    reward_thread.start()
    assert not reward_entered.wait(timeout=0.05)
    release_action.set()
    action_thread.join(timeout=2)
    reward_thread.join(timeout=2)

    assert reward_entered.is_set()
    assert session.action_history == ["TYPING"]
    assert service._release_worker.enqueued == [session]
    assert len(results) == 2


def test_identity_guard_does_not_end_reused_session_id() -> None:
    registry = SessionRegistry()
    old = SessionState(
        task_id="task-id",
        lease=Lease(context_id="old", port=3000),
        release_hooks=[],
    )
    new = SessionState(
        task_id="task-id",
        lease=Lease(context_id="new", port=3001),
        release_hooks=[],
    )
    registry.start_session(1, old)

    with registry.session_operation(1, "task-id", reward=True) as operation:
        registry.end_session(1)
        registry.start_session(1, new)
        registry.end_session_if_current(operation)

    assert registry.require_session_state(1, "task-id") is new
