import base64
import hashlib
import sqlite3
from pathlib import Path
from threading import Event
from typing import Any, cast

from fastapi.testclient import TestClient
from surfgym_contracts.command import Command
from surfgym_contracts.protocol.artifact import ArtifactPayload, ArtifactSpec
from surfgym_contracts.protocol.upstream_to_gateway import (
    ExecuteResponse,
    MasterAllocateResponse,
    MasterReleaseResponse,
    ObserveResponse,
    ScreenshotResponse,
)
from surfgym_contracts.task import Criteria, Hook, Task, Website
from surfgym_runtime.gateway.error import Deadline
from surfgym_runtime.gateway.registry import SessionRegistry
from surfgym_runtime.gateway.server import create_app
from surfgym_runtime.gateway.service import Service
from surfgym_runtime.gateway.transport import GatewayTransport
from surfgym_runtime.gateway.worker import ReleaseWorker
from surfgym_runtime.support import Config, Evaluator, TaskStore
from surfgym_runtime.support.config import GatewayConfig, ProcessTimeout, WavepoolConfig

_ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class HybridRecordingTransport:
    def __init__(self) -> None:
        self.allocated_websites: list[Website] = []
        self.commands: list[Command] = []
        self.release_calls: list[tuple[str, list[Hook]]] = []
        self.artifact_calls: list[tuple[str, ArtifactSpec, float]] = []
        self.released = Event()

    def allocate(
        self,
        *,
        deadline: Deadline,
        websites: list[Website],
        allocate_hooks: list[Hook],
        release_hooks: list[Hook],
    ) -> MasterAllocateResponse:
        self.allocated_websites = websites
        return MasterAllocateResponse(
            context_id="hybrid-context",
            instance_host="127.0.0.1",
            instance_port=58020,
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
        self.commands.append(command)
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
        return ObserveResponse(observation=["ready", "saved"])

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

    def artifact(
        self,
        *,
        context_id: str,
        instance_port: int,
        artifact: ArtifactSpec,
        timeout: float,
    ) -> ArtifactPayload:
        assert instance_port == 58020
        self.artifact_calls.append((context_id, artifact, timeout))
        raw = b"saved"
        return ArtifactPayload(
            path=artifact.path,
            mime_type="text/plain",
            sha256=hashlib.sha256(raw).hexdigest(),
            size=len(raw),
            encoding="base64",
            data=base64.b64encode(raw).decode("ascii"),
        )


def _write_task_database(path: Path, task: Task) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE tasks (task_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO tasks (task_id, payload) VALUES (?, ?)",
            (task.task_id, task.model_dump_json()),
        )


def _config(task_path: Path, log_path: Path) -> Config:
    process_timeout = ProcessTimeout(
        allocate=0.01,
        release=0.01,
        screenshot=0.01,
        observe=0.01,
        execute=0.01,
        layer_gap=0.0,
    )
    return Config(
        task_file_path=task_path,
        log_path=log_path,
        gateway=GatewayConfig(
            host="127.0.0.1",
            port=58000,
            gateway_workers=1,
            gateway_in_flight=1,
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
            process_timeout=process_timeout,
        ),
    )


def test_hybrid_gateway_service_http_cycle_preserves_surfaces_and_releases(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    release_hook = Hook(
        website_id="native",
        timing="before",
        script="window.releaseFixture()",
    )
    task = Task.model_validate(
        {
            "task_id": "hybrid-http-cycle",
            "instruction": "Read the web surface and finish the native task.",
            "website": [
                {
                    "website_id": "web",
                    "url": "http://web.localhost:3200",
                    "surface": "web",
                },
                {
                    "website_id": "native",
                    "url": "http://desktop.localhost:55301/gimp",
                    "surface": "native",
                },
            ],
            "evaluation": {
                "mode": "criteria",
                "operator": "and",
                "criteria": [
                    {"website_id": "web", "value": "ready"},
                    {"website_id": "native", "value": "saved"},
                ],
            },
            "lifecycle_hooks": {"release": [release_hook.model_dump()]},
        }
    )
    database_path = tmp_path / "tasks.sqlite3"
    _write_task_database(database_path, task)
    transport = HybridRecordingTransport()

    def service_factory(*, task_store: TaskStore, wavepool_config: WavepoolConfig) -> Service:
        service: Any = object.__new__(Service)
        service.task_store = task_store
        service.evaluator = Evaluator()
        service.transport = transport
        service._session_registry = SessionRegistry()
        service._release_worker = ReleaseWorker(
            transport=cast(GatewayTransport, transport),
            release_timeout=1.0,
        )
        service.process_timeout = wavepool_config.process_timeout
        return cast(Service, service)

    monkeypatch.setattr("surfgym_runtime.gateway.server.Service", service_factory)
    app = create_app(_config(database_path, tmp_path / "gateway.log"))

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        start = client.post(
            "/",
            json={"op": "start", "session_id": 41, "task_id": task.task_id},
        )
        move_web = client.post(
            "/",
            json={
                "op": "action",
                "session_id": 41,
                "task_id": task.task_id,
                "actions": [{"action_type": "MOVE_TO", "x": 100, "y": 100}],
            },
        )
        move_native = client.post(
            "/",
            json={
                "op": "action",
                "session_id": 41,
                "task_id": task.task_id,
                "actions": [{"action_type": "MOVE_TO", "x": 1200, "y": 100}],
            },
        )
        wait = client.post(
            "/",
            json={
                "op": "action",
                "session_id": 41,
                "task_id": task.task_id,
                "actions": [{"action_type": "WAIT"}],
            },
        )
        done = client.post(
            "/",
            json={
                "op": "action",
                "session_id": 41,
                "task_id": task.task_id,
                "actions": [{"action_type": "DONE"}],
            },
        )
        reward = client.post(
            "/",
            json={
                "op": "reward",
                "session_id": 41,
                "task_id": task.task_id,
                "artifacts": [{"path": "Desktop/out.txt", "max_bytes": 128}],
            },
        )

        assert all(
            response.status_code == 200
            for response in (start, move_web, move_native, wait, done, reward)
        )
        assert reward.json()["reward"] == 1.0
        assert [artifact["path"] for artifact in reward.json()["artifacts"]] == ["Desktop/out.txt"]
        assert transport.released.wait(timeout=1.0)

    assert [(website.website_id, website.surface) for website in transport.allocated_websites] == [
        ("web", "web"),
        ("native", "native"),
    ]
    assert [command.command for command in transport.commands] == [
        "mouse_move",
        "mouse_move",
        "sleep",
    ]
    assert transport.release_calls == [("hybrid-context", [release_hook])]
    assert len(transport.artifact_calls) == 1
    context_id, artifact, timeout = transport.artifact_calls[0]
    assert context_id == "hybrid-context"
    assert artifact == ArtifactSpec(path="Desktop/out.txt", max_bytes=128)
    assert 34.0 < timeout <= 35.0
