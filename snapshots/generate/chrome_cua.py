"""Host-only CUA validation runner for the Chrome fixture.

The runner speaks only the SurfGym agent gateway protocol.  It deliberately
does not use Chrome DevTools or a browser automation client.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, model_validator
from surfgym_contracts.protocol.agent_to_gateway import (
    ActionRequest,
    RewardRequest,
    StartRequest,
)
from surfgym_contracts.protocol.gateway_to_agent import (
    ActionResponse,
    ErrorResponse,
    Response,
    ResponseAdapter,
    RewardResponse,
)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ChromeProvenance(_FrozenModel):
    """The canonical Docker Chrome image/profile provenance record."""

    acceptance_state: str
    candidate_baseline: str
    target_chrome_major: int
    functional_compatibility_status: str
    chrome_distribution: str
    chrome_for_testing_version: str
    chrome_for_testing_linux64_url: str
    chrome_for_testing_linux64_sha256: str
    required_functional_flows: list[str] = Field(min_length=1)
    final_base_image_digest: str
    final_fixture_image_digest: str
    final_profile_template_sha256: str

    @model_validator(mode="after")
    def require_evidence_when_accepted(self) -> ChromeProvenance:
        values = (
            self.chrome_for_testing_version,
            self.chrome_for_testing_linux64_sha256,
            self.final_base_image_digest,
            self.final_fixture_image_digest,
            self.final_profile_template_sha256,
        )
        has_pending_value = any(
            value is None or value.strip().lower() in {"", "pending"} for value in values
        )
        compatibility_not_proven = self.functional_compatibility_status.strip().lower() in {
            "",
            "pending",
            "not-run",
        }
        if self.acceptance_state == "accepted" and (
            has_pending_value or compatibility_not_proven
        ):
            raise ValueError(
                "accepted provenance requires completed functional compatibility and non-pending "
                "version, hash, and final image/profile digest evidence"
            )
        return self


class ActionCase(_FrozenModel):
    name: str
    task_id: str
    session_id: int
    expected_reward: float
    actions: list[list[dict[str, Any]]] = Field(default_factory=list)


class ValidationPlan(_FrozenModel):
    cases: list[ActionCase] = Field(min_length=1)


def default_validation_plan(*, base_session_id: int) -> ValidationPlan:
    """Return the fixed, visible-GUI smoke controls for the Chrome task corpus."""
    password_task_id = "open_etsy_password_entry_0_1"
    infeasible_task_id = "set_chrome_interface_language_to_toki_pona"
    return ValidationPlan(
        cases=[
            ActionCase(
                name="password-manager-initial",
                task_id=password_task_id,
                session_id=base_session_id,
                expected_reward=0.0,
            ),
            ActionCase(
                name="password-manager-action",
                task_id=password_task_id,
                session_id=base_session_id + 1,
                expected_reward=1.0,
                actions=[
                    [{"action_type": "HOTKEY", "keys": ["Control", "l"]}],
                    [
                        {
                            "action_type": "TYPING",
                            "text": "chrome://password-manager/passwords",
                        }
                    ],
                    [{"action_type": "PRESS", "key": "Enter"}],
                    [{"action_type": "WAIT"}],
                ],
            ),
            ActionCase(
                name="infeasible-done",
                task_id=infeasible_task_id,
                session_id=base_session_id + 2,
                expected_reward=0.0,
                actions=[[{"action_type": "DONE"}]],
            ),
            ActionCase(
                name="infeasible-fail",
                task_id=infeasible_task_id,
                session_id=base_session_id + 3,
                expected_reward=1.0,
                actions=[[{"action_type": "FAIL"}]],
            ),
        ]
    )


class GatewayTransport(Protocol):
    def post(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> Response: ...


class FixtureHealthTransport(Protocol):
    def get(self, *, url: str, timeout_seconds: float) -> dict[str, Any]: ...


class GatewayHttpTransport:
    """The sole network boundary used by the runner."""

    def post(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> Response:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as http_response:
                return ResponseAdapter.validate_json(http_response.read())
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GatewayHttpError(url=url, status=exc.code, body=body) from exc
        except URLError as exc:
            raise GatewayHttpError(url=url, status=None, body=str(exc)) from exc


class FixtureHealthHttpTransport:
    """Read the Docker Gateway's authoritative slot-state endpoint."""

    def get(self, *, url: str, timeout_seconds: float) -> dict[str, Any]:
        try:
            with urlopen(url, timeout=timeout_seconds) as http_response:
                payload = json.loads(http_response.read())
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GatewayHttpError(url=url, status=exc.code, body=body) from exc
        except (URLError, json.JSONDecodeError) as exc:
            raise GatewayHttpError(url=url, status=None, body=str(exc)) from exc

        if not isinstance(payload, dict):
            raise GatewayHttpError(url=url, status=None, body="health response must be an object")
        return payload


class ChromeCuaError(RuntimeError):
    pass


class GatewayHttpError(ChromeCuaError):
    def __init__(self, *, url: str, status: int | None, body: str) -> None:
        self.url = url
        self.status = status
        self.body = body
        super().__init__(f"Gateway HTTP request failed (status={status}): {body}")


class GatewayResponseError(ChromeCuaError):
    def __init__(self, *, operation: str, response: ErrorResponse) -> None:
        self.operation = operation
        self.response = response
        super().__init__(f"Gateway {operation} failed: {response.message}")


class ProtocolContractError(ChromeCuaError):
    pass


class RewardMismatchError(ChromeCuaError):
    pass


class FixtureHealthError(ChromeCuaError):
    def __init__(self, message: str, *, evidence: dict[str, Any]) -> None:
        self.evidence = evidence
        super().__init__(message)


class ChromeCuaRunner:
    def __init__(
        self,
        *,
        gateway_url: str,
        fixture_health_url: str,
        timeout_seconds: float,
        health_timeout_seconds: float | None = None,
        health_poll_interval_seconds: float = 1.0,
        output_dir: Path,
        transport: GatewayTransport | None = None,
        health_transport: FixtureHealthTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if health_timeout_seconds is None:
            health_timeout_seconds = timeout_seconds
        if health_timeout_seconds <= 0 or health_timeout_seconds > timeout_seconds:
            raise ValueError("health_timeout_seconds must be > 0 and <= timeout_seconds")
        if health_poll_interval_seconds <= 0:
            raise ValueError("health_poll_interval_seconds must be > 0")
        self.gateway_url = gateway_url
        self.fixture_health_url = fixture_health_url
        self.timeout_seconds = timeout_seconds
        self.health_timeout_seconds = health_timeout_seconds
        self.health_poll_interval_seconds = health_poll_interval_seconds
        self.output_dir = output_dir
        self.transport = transport or GatewayHttpTransport()
        self.health_transport = health_transport or FixtureHealthHttpTransport()
        self.sleep = sleep
        self.monotonic = monotonic
        self.manifest_path = self.output_dir / "manifest.json"

    def run(self, *, plan: ValidationPlan, provenance: ChromeProvenance) -> Path:
        self._require_fresh_session_ids(plan)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "run_status": "running",
            "gateway_url": self.gateway_url,
            "fixture_health_url": self.fixture_health_url,
            "timeout_seconds": self.timeout_seconds,
            "health_timeout_seconds": self.health_timeout_seconds,
            "health_poll_interval_seconds": self.health_poll_interval_seconds,
            "provenance": provenance.model_dump(mode="json"),
            "cases": [],
        }
        self._write_manifest(manifest)

        try:
            for case in plan.cases:
                case_record: dict[str, Any] = {
                    "name": case.name,
                    "task_id": case.task_id,
                    "session_id": case.session_id,
                    "expected_reward": case.expected_reward,
                    "events": [],
                }
                manifest["cases"].append(case_record)
                self._write_manifest(manifest)

                self._wait_and_record_fixture_health(
                    case_record=case_record,
                    field="start_readiness",
                    manifest=manifest,
                )
                self._send_start(case=case, case_record=case_record, manifest=manifest)
                for actions in case.actions:
                    self._send_action(
                        case=case,
                        actions=actions,
                        case_record=case_record,
                        manifest=manifest,
                    )
                try:
                    reward = self._send_reward(
                        case=case,
                        case_record=case_record,
                        manifest=manifest,
                    )
                finally:
                    self._wait_and_record_fixture_health(
                        case_record=case_record,
                        field="release",
                        manifest=manifest,
                        require_release_transition=True,
                    )
                if reward != case.expected_reward:
                    raise RewardMismatchError(
                        f"{case.name} expected reward {case.expected_reward}, got {reward}"
                    )
                case_record["result"] = {
                    "status": "passed",
                    "reward": reward,
                    "release_requested": True,
                }
                self._write_manifest(manifest)
        except Exception as exc:
            manifest["run_status"] = "failed"
            manifest["error"] = {"type": type(exc).__name__, "message": str(exc)}
            self._write_manifest(manifest)
            raise

        manifest["run_status"] = "passed"
        self._write_manifest(manifest)
        return self.manifest_path

    def _send_start(
        self,
        *,
        case: ActionCase,
        case_record: dict[str, Any],
        manifest: dict[str, Any],
    ) -> None:
        request = StartRequest(op="start", session_id=case.session_id, task_id=case.task_id)
        self._request(
            operation="start",
            payload=request.model_dump(mode="json", exclude_defaults=True),
            case=case,
            case_record=case_record,
            manifest=manifest,
        )

    def _send_action(
        self,
        *,
        case: ActionCase,
        actions: list[dict[str, Any]],
        case_record: dict[str, Any],
        manifest: dict[str, Any],
    ) -> None:
        request = ActionRequest(
            op="action",
            session_id=case.session_id,
            task_id=case.task_id,
            actions=actions,
        )
        self._request(
            operation="action",
            payload=request.model_dump(mode="json", exclude_defaults=True),
            case=case,
            case_record=case_record,
            manifest=manifest,
        )

    def _send_reward(
        self,
        *,
        case: ActionCase,
        case_record: dict[str, Any],
        manifest: dict[str, Any],
    ) -> float:
        request = RewardRequest(op="reward", session_id=case.session_id, task_id=case.task_id)
        response = self._request(
            operation="reward",
            payload=request.model_dump(mode="json", exclude_defaults=True),
            case=case,
            case_record=case_record,
            manifest=manifest,
        )
        if not isinstance(response, RewardResponse):
            raise ProtocolContractError(
                f"reward returned {type(response).__name__}, expected RewardResponse"
            )
        return response.reward

    def _request(
        self,
        *,
        operation: str,
        payload: dict[str, Any],
        case: ActionCase,
        case_record: dict[str, Any],
        manifest: dict[str, Any],
    ) -> Response:
        event: dict[str, Any] = {"operation": operation, "request": payload}
        case_record["events"].append(event)
        try:
            response = self.transport.post(
                url=self.gateway_url,
                payload=payload,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception as exc:
            event["error"] = {"type": type(exc).__name__, "message": str(exc)}
            self._write_manifest(manifest)
            raise

        event["response"] = response.model_dump(mode="json", by_alias=True)
        self._record_artifact(case=case, event=event, response=response)
        self._write_manifest(manifest)
        self._require_response_identity(case=case, operation=operation, response=response)
        if isinstance(response, ErrorResponse):
            raise GatewayResponseError(operation=operation, response=response)
        return response

    def _wait_for_fixture_ready(self, *, require_release_transition: bool = False) -> dict[str, Any]:
        """Wait for exactly one reusable slot after asynchronous fixture release."""
        started_at = self.monotonic()
        deadline = started_at + self.health_timeout_seconds
        polls: list[dict[str, Any]] = []
        release_transition_observed = False

        while True:
            now = self.monotonic()
            remaining = deadline - now
            if remaining <= 0:
                raise FixtureHealthError(
                    "fixture did not become exactly-one-idle-slot ready before health timeout; "
                    f"last poll={polls[-1] if polls else None}",
                    evidence={"status": "timeout", "polls": polls},
                )

            try:
                payload = self.health_transport.get(
                    url=self.fixture_health_url,
                    timeout_seconds=min(self.timeout_seconds, remaining),
                )
                slot_states = payload.get("slot_states")
            except Exception as exc:
                polls.append(
                    {
                        "elapsed_seconds": round(now - started_at, 3),
                        "error": {"type": type(exc).__name__, "message": str(exc)},
                    }
                )
            else:
                poll = {
                    "elapsed_seconds": round(now - started_at, 3),
                    "slot_states": slot_states,
                }
                polls.append(poll)
                if self._is_fixture_ready(slot_states):
                    if not require_release_transition or release_transition_observed:
                        return {
                            "status": "ready",
                            "release_transition_observed": release_transition_observed,
                            "polls": polls,
                        }
                elif isinstance(slot_states, dict):
                    # A reward reply is asynchronous. A stale idle sample is
                    # not evidence that *this* reward's release completed.
                    release_transition_observed = True
                if isinstance(slot_states, dict) and slot_states.get("broken", 0) != 0:
                    raise FixtureHealthError(
                        "fixture reports broken slot state; "
                        f"last poll={poll}",
                        evidence={"status": "broken", "polls": polls},
                    )

            if self.monotonic() >= deadline:
                raise FixtureHealthError(
                    "fixture did not become exactly-one-idle-slot ready before health timeout; "
                    f"last poll={polls[-1]}",
                    evidence={"status": "timeout", "polls": polls},
                )
            self.sleep(self.health_poll_interval_seconds)

    def _wait_and_record_fixture_health(
        self,
        *,
        case_record: dict[str, Any],
        field: str,
        manifest: dict[str, Any],
        require_release_transition: bool = False,
    ) -> None:
        try:
            case_record[field] = self._wait_for_fixture_ready(
                require_release_transition=require_release_transition
            )
        except FixtureHealthError as exc:
            case_record[field] = exc.evidence
            self._write_manifest(manifest)
            raise
        self._write_manifest(manifest)

    @staticmethod
    def _is_fixture_ready(slot_states: object) -> bool:
        return isinstance(slot_states, dict) and slot_states == {
            "idle": 1,
            "resetting": 0,
            "busy": 0,
            "broken": 0,
        }

    def _record_artifact(self, *, case: ActionCase, event: dict[str, Any], response: Response) -> None:
        image = response.image if isinstance(response, (ActionResponse, RewardResponse)) else None
        if image is None or not image.data:
            event["artifact_path"] = None
            return

        artifact_dir = self.output_dir / "artifacts" / f"{case.session_id}-{case.name}"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        event_index = sum(1 for _ in artifact_dir.iterdir())
        artifact_path = artifact_dir / f"{event_index:02d}.png"
        artifact_path.write_bytes(base64.b64decode(image.data, validate=True))
        event["artifact_path"] = str(artifact_path.relative_to(self.output_dir))

    def _require_response_identity(
        self,
        *,
        case: ActionCase,
        operation: str,
        response: Response,
    ) -> None:
        if response.session_id != case.session_id or response.task_id != case.task_id:
            raise ProtocolContractError(
                f"{operation} response identity mismatch: expected "
                f"({case.session_id}, {case.task_id}), got "
                f"({response.session_id}, {response.task_id})"
            )

    def _require_fresh_session_ids(self, plan: ValidationPlan) -> None:
        session_ids = [case.session_id for case in plan.cases]
        if len(session_ids) != len(set(session_ids)):
            raise ValueError("each reward check must use a fresh session_id")

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
