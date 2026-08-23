import sqlite3
import time
from pathlib import Path
from threading import Event
from typing import Any, cast

import pytest
from surfgym_contracts.command import Command
from surfgym_contracts.computer13 import FailAction
from surfgym_contracts.protocol.agent_to_gateway import (
    ActionRequest,
    RewardRequest,
    StartRequest,
)
from surfgym_contracts.protocol.upstream_to_gateway import (
    ExecuteResponse,
    MasterAllocateResponse,
    MasterReleaseResponse,
    ObserveResponse,
    ScreenshotResponse,
)
from surfgym_contracts.task import (
    Criteria,
    Hook,
    InfeasibleEvaluation,
    LifecycleHooks,
    Task,
    Website,
)
from surfgym_runtime.gateway.error import Deadline, InvalidRequest
from surfgym_runtime.gateway.registry import SessionRegistry
from surfgym_runtime.gateway.service import Service
from surfgym_runtime.gateway.transport import GatewayTransport
from surfgym_runtime.gateway.worker import ReleaseWorker
from surfgym_runtime.support import Evaluator, TaskStore
from surfgym_runtime.support.config import ProcessTimeout

_ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42Y"
    "AAAAASUVORK5CYII="
)


class RecordingTransport:
    def __init__(self) -> None:
        self.execute_calls: list[Command] = []
        self.observe_calls: list[list[Criteria]] = []
        self.release_calls: list[tuple[str, list[Hook]]] = []
        self.released = Event()

    def allocate(
        self,
        *,
        deadline: Deadline,
        websites: list[Website],
        allocate_hooks: list[Hook],
        release_hooks: list[Hook],
    ) -> MasterAllocateResponse:
        return MasterAllocateResponse(
            context_id="context-id",
            instance_host="127.0.0.1",
            instance_port=3000,
        )

    def screenshot(
        self,
        deadline: Deadline,
        context_id: str,
        instance_port: int,
    ) -> ScreenshotResponse:
        return ScreenshotResponse(
            screenshot_b64=_ONE_PIXEL_PNG,
            media_type="image/png",
            x=0,
            y=0,
        )

    def execute(
        self,
        deadline: Deadline,
        context_id: str,
        instance_port: int,
        command: Command,
    ) -> ExecuteResponse:
        self.execute_calls.append(command)
        return ExecuteResponse()

    def observe(
        self,
        *,
        deadline: Deadline,
        context_id: str,
        instance_port: int,
        criteria: list[Criteria],
        observe_hooks: list[Hook],
    ) -> ObserveResponse:
        self.observe_calls.append(criteria)
        return ObserveResponse(observation=[])

    def release(
        self,
        *,
        deadline: Deadline,
        context_id: str,
        release_hooks: list[Hook],
    ) -> MasterReleaseResponse:
        self.release_calls.append((context_id, release_hooks))
        self.released.set()
        return MasterReleaseResponse()


def _write_task_store(path: Path, task: Task) -> TaskStore:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE tasks (task_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO tasks (task_id, payload) VALUES (?, ?)",
            (task.task_id, task.model_dump_json()),
        )
    return TaskStore(path)


def test_infeasible_request_cycle_reaches_async_release(tmp_path: Path) -> None:
    release_hook = Hook(timing="before", script="window.releaseFixture()")
    task = Task(
        task_id="infeasible-task",
        instruction="Report that this task is infeasible.",
        website=[Website(url="http://example.test")],
        evaluation=InfeasibleEvaluation(),
        lifecycle_hooks=LifecycleHooks(release=[release_hook]),
    )
    task_store = _write_task_store(tmp_path / "tasks.sqlite3", task)
    transport = RecordingTransport()

    service: Any = object.__new__(Service)
    service.task_store = task_store
    service.evaluator = Evaluator()
    service.transport = transport
    service._session_registry = SessionRegistry()
    service._release_worker = ReleaseWorker(
        transport=cast(GatewayTransport, transport),
        release_timeout=1.0,
    )
    service.process_timeout = ProcessTimeout(
        allocate=0.01,
        release=0.01,
        screenshot=0.01,
        observe=0.01,
        execute=0.01,
        layer_gap=0.0,
    )
    service.open()

    try:
        start_response = service.handle_request(
            StartRequest(op="start", session_id=1, task_id=task.task_id),
            deadline_at=time.monotonic() + 5.0,
        )
        action_response = service.handle_request(
            ActionRequest(
                op="action",
                session_id=1,
                task_id=task.task_id,
                actions=[FailAction(action_type="FAIL")],
            ),
            deadline_at=time.monotonic() + 5.0,
        )
        reward_response = service.handle_request(
            RewardRequest(op="reward", session_id=1, task_id=task.task_id),
            deadline_at=time.monotonic() + 5.0,
        )

        assert start_response.task_id == task.task_id
        assert action_response.task_id == task.task_id
        assert reward_response.reward == 1.0
        assert transport.released.wait(timeout=1.0)
        assert transport.release_calls == [("context-id", [release_hook])]
        assert transport.execute_calls == []
        assert transport.observe_calls == []
        with pytest.raises(InvalidRequest, match="not active"):
            service._session_registry.require_session_state(1, task.task_id)
    finally:
        service.close()
        task_store.close()
