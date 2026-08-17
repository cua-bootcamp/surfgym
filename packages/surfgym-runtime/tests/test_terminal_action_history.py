from collections.abc import Callable
from typing import Any

import pytest
from surfgym_contracts.command import Command
from surfgym_contracts.computer13 import Computer13, DoneAction, FailAction, TypingAction
from surfgym_contracts.protocol.agent_to_gateway import ActionRequest
from surfgym_runtime.gateway.error import Deadline, InvalidRequest
from surfgym_runtime.gateway.registry import Lease, SessionRegistry, SessionState
from surfgym_runtime.gateway.service import Service


def _deadline(context: str) -> Deadline:
    return Deadline(float("inf"), context)


def _service_with_session() -> tuple[Any, SessionState, list[Command]]:
    service: Any = object.__new__(Service)
    service._session_registry = SessionRegistry()
    executed: list[Command] = []

    def execute(
        deadline: Callable[[str], Deadline], lease: Lease, command: Command
    ) -> None:
        executed.append(command)

    def screenshot(
        deadline: Callable[[str], Deadline], lease: Lease
    ) -> tuple[str, str]:
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

    def fail_execute(
        deadline: Callable[[str], Deadline], lease: Lease, command: Command
    ) -> None:
        raise RuntimeError("execute failed")

    service._execute = fail_execute

    with pytest.raises(RuntimeError, match="execute failed"):
        service._handle_action(
            _request(TypingAction(action_type="TYPING", text="x")),
            _deadline,
        )

    assert session.action_history == []
    assert executed == []
