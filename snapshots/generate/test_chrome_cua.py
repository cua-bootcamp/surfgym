import base64
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from surfgym_contracts.protocol.gateway_to_agent import ResponseAdapter

sys.path.insert(0, str(Path(__file__).parent))

import chrome_cua
from chrome_cua import (
    ActionCase,
    ChromeCuaRunner,
    ChromeProvenance,
    FixtureHealthError,
    GatewayResponseError,
    RewardMismatchError,
    ValidationPlan,
)

_ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42Y"
    "AAAAASUVORK5CYII="
)


_CANONICAL_PROVENANCE = {
    "acceptance_state": "candidate",
    "candidate_baseline": "shared-chrome-120",
    "target_chrome_major": 120,
    "functional_compatibility_status": "not-run",
    "chrome_distribution": "chrome-for-testing",
    "chrome_for_testing_version": "120.0.6099.109",
    "chrome_for_testing_linux64_url": (
        "https://storage.googleapis.com/chrome-for-testing-public/120.0.6099.109/"
        "linux64/chrome-linux64.zip"
    ),
    "chrome_for_testing_linux64_sha256": "bcb22c5242aabf184c6fadd86ee58b3ae35739177edac9de3938ed33791d4ddf",
    "required_functional_flows": [
        "password-manager",
        "appearance",
        "on-exit-site-data",
        "shortcut",
        "unpacked-extension",
        "bing",
        "pdf",
    ],
    "final_base_image_digest": "pending",
    "final_fixture_image_digest": "pending",
    "final_profile_template_sha256": "pending",
}


class RecordingTransport:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def post(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ):
        assert url == "http://127.0.0.1:18000/"
        assert timeout_seconds == 17.0
        self.requests.append(payload)
        return ResponseAdapter.validate_python(self.responses.pop(0))


class RecordingFixtureHealthTransport:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[str, float]] = []

    def get(self, *, url: str, timeout_seconds: float) -> dict[str, Any]:
        self.requests.append((url, timeout_seconds))
        return self.responses.pop(0)


class AlwaysReadyFixtureHealthTransport:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, *, url: str, timeout_seconds: float) -> dict[str, Any]:
        assert url == "http://127.0.0.1:53101/health"
        assert timeout_seconds > 0
        state = self.calls % 3
        self.calls += 1
        if state == 1:
            return {"slot_states": {"idle": 0, "resetting": 1, "busy": 0, "broken": 0}}
        return {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}}


def _action_response(session_id: int, task_id: str) -> dict[str, Any]:
    return {
        "status": "ok",
        "session_id": session_id,
        "task_id": task_id,
        "image": {"data": _ONE_PIXEL_PNG, "mimeType": "image/png"},
    }


def _reward_response(session_id: int, task_id: str, reward: float) -> dict[str, Any]:
    return {
        "status": "ok",
        "session_id": session_id,
        "task_id": task_id,
        "reward": reward,
        "image": None,
    }


def _provenance() -> ChromeProvenance:
    return ChromeProvenance.model_validate(_CANONICAL_PROVENANCE)


def test_runner_serializes_password_manager_protocol_and_manifest(tmp_path: Path) -> None:
    """Fails if a CUA action is skipped, payload fields drift, or artifacts are not recorded."""
    task_id = "12086550-11c0-466b-b367-1d9e75b3910e_0_1"
    responses = [
        _action_response(100, task_id),
        _reward_response(100, task_id, 0.0),
        _action_response(101, task_id),
        *[_action_response(101, task_id) for _ in range(4)],
        _reward_response(101, task_id, 1.0),
    ]
    transport = RecordingTransport(responses)
    plan = ValidationPlan(
        cases=[
            ActionCase(name="initial", task_id=task_id, session_id=100, expected_reward=0.0),
            ActionCase(
                name="password-manager",
                task_id=task_id,
                session_id=101,
                expected_reward=1.0,
                actions=[
                    [{"action_type": "HOTKEY", "keys": ["Control", "l"]}],
                    [{"action_type": "TYPING", "text": "chrome://password-manager/passwords"}],
                    [{"action_type": "PRESS", "key": "Enter"}],
                    [{"action_type": "WAIT"}],
                ],
            ),
        ]
    )

    manifest_path = ChromeCuaRunner(
        gateway_url="http://127.0.0.1:18000/",
        fixture_health_url="http://127.0.0.1:53101/health",
        timeout_seconds=17.0,
        output_dir=tmp_path,
        transport=transport,
        health_transport=AlwaysReadyFixtureHealthTransport(),
    ).run(plan=plan, provenance=_provenance())

    assert transport.requests == [
        {"op": "start", "session_id": 100, "task_id": task_id},
        {"op": "reward", "session_id": 100, "task_id": task_id},
        {"op": "start", "session_id": 101, "task_id": task_id},
        {
            "op": "action",
            "session_id": 101,
            "task_id": task_id,
            "actions": [{"action_type": "HOTKEY", "keys": ["Control", "l"]}],
        },
        {
            "op": "action",
            "session_id": 101,
            "task_id": task_id,
            "actions": [
                {"action_type": "TYPING", "text": "chrome://password-manager/passwords"}
            ],
        },
        {
            "op": "action",
            "session_id": 101,
            "task_id": task_id,
            "actions": [{"action_type": "PRESS", "key": "Enter"}],
        },
        {
            "op": "action",
            "session_id": 101,
            "task_id": task_id,
            "actions": [{"action_type": "WAIT"}],
        },
        {"op": "reward", "session_id": 101, "task_id": task_id},
    ]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_status"] == "passed"
    assert manifest["cases"][1]["result"] == {
        "status": "passed",
        "reward": 1.0,
        "release_requested": True,
    }
    assert len(manifest["cases"][1]["events"]) == 6
    artifact = manifest["cases"][1]["events"][0]["artifact_path"]
    assert artifact is not None
    assert (tmp_path / artifact).read_bytes() == base64.b64decode(_ONE_PIXEL_PNG)


def test_runner_enforces_fresh_sessions_across_reward_checks(tmp_path: Path) -> None:
    """Fails if initial and action checks can accidentally share a released session."""
    task_id = "task-id"
    plan = ValidationPlan(
        cases=[
            ActionCase(name="initial", task_id=task_id, session_id=7, expected_reward=0.0),
            ActionCase(name="action", task_id=task_id, session_id=7, expected_reward=1.0),
        ]
    )

    with pytest.raises(ValueError, match="fresh session_id"):
        ChromeCuaRunner(
            gateway_url="http://127.0.0.1:18000/",
            fixture_health_url="http://127.0.0.1:53101/health",
            timeout_seconds=17.0,
            output_dir=tmp_path,
            transport=RecordingTransport([]),
            health_transport=AlwaysReadyFixtureHealthTransport(),
        ).run(plan=plan, provenance=_provenance())


def test_runner_waits_for_one_idle_fixture_slot_before_start_and_after_reward(
    tmp_path: Path,
) -> None:
    """Fails if fresh CUA sessions can start while the prior release is still resetting."""
    task_id = "task-id"
    gateway_transport = RecordingTransport(
        [
            _action_response(10, task_id),
            _reward_response(10, task_id, 0.0),
            _action_response(11, task_id),
            _reward_response(11, task_id, 1.0),
        ]
    )
    health_transport = RecordingFixtureHealthTransport(
        [
            {"slot_states": {"idle": 0, "resetting": 1, "busy": 0, "broken": 0}},
            {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
            {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
            {"slot_states": {"idle": 0, "resetting": 1, "busy": 0, "broken": 0}},
            {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
            {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
            {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
            {"slot_states": {"idle": 0, "resetting": 1, "busy": 0, "broken": 0}},
            {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
        ]
    )
    slept: list[float] = []

    manifest_path = ChromeCuaRunner(
        gateway_url="http://127.0.0.1:18000/",
        fixture_health_url="http://127.0.0.1:53101/health",
        timeout_seconds=17.0,
        health_timeout_seconds=17.0,
        health_poll_interval_seconds=0.25,
        output_dir=tmp_path,
        transport=gateway_transport,
        health_transport=health_transport,
        sleep=slept.append,
    ).run(
        plan=ValidationPlan(
            cases=[
                ActionCase(name="initial", task_id=task_id, session_id=10, expected_reward=0.0),
                ActionCase(name="action", task_id=task_id, session_id=11, expected_reward=1.0),
            ]
        ),
        provenance=_provenance(),
    )

    assert gateway_transport.requests == [
        {"op": "start", "session_id": 10, "task_id": task_id},
        {"op": "reward", "session_id": 10, "task_id": task_id},
        {"op": "start", "session_id": 11, "task_id": task_id},
        {"op": "reward", "session_id": 11, "task_id": task_id},
    ]
    assert health_transport.requests == [("http://127.0.0.1:53101/health", 17.0)] * 9
    assert slept == [0.25, 0.25, 0.25, 0.25, 0.25]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["fixture_health_url"] == "http://127.0.0.1:53101/health"
    assert [
        poll["slot_states"]
        for poll in manifest["cases"][0]["start_readiness"]["polls"]
    ] == [
        {"idle": 0, "resetting": 1, "busy": 0, "broken": 0},
        {"idle": 1, "resetting": 0, "busy": 0, "broken": 0},
    ]
    assert manifest["cases"][0]["release"]["status"] == "ready"
    assert manifest["cases"][1]["start_readiness"]["status"] == "ready"
    assert [
        poll["slot_states"]
        for poll in manifest["cases"][1]["start_readiness"]["polls"]
    ] == [
        {"idle": 1, "resetting": 0, "busy": 0, "broken": 0},
    ]


def test_runner_records_broken_fixture_health_in_failed_manifest(tmp_path: Path) -> None:
    """Fails if a broken slot aborts CUA without preserving the observed health state."""
    runner = ChromeCuaRunner(
        gateway_url="http://127.0.0.1:18000/",
        fixture_health_url="http://127.0.0.1:53101/health",
        timeout_seconds=17.0,
        output_dir=tmp_path,
        transport=RecordingTransport([]),
        health_transport=RecordingFixtureHealthTransport(
            [{"slot_states": {"idle": 0, "resetting": 0, "busy": 0, "broken": 1}}]
        ),
    )

    with pytest.raises(FixtureHealthError, match="broken slot"):
        runner.run(
            plan=ValidationPlan(
                cases=[ActionCase(name="initial", task_id="task-id", session_id=99, expected_reward=0.0)]
            ),
            provenance=_provenance(),
        )

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_status"] == "failed"
    assert manifest["cases"][0]["start_readiness"] == {
        "status": "broken",
        "polls": [
            {
                "elapsed_seconds": 0.0,
                "slot_states": {"idle": 0, "resetting": 0, "busy": 0, "broken": 1},
            }
        ],
    }


def test_runner_waits_for_release_after_reward_mismatch(tmp_path: Path) -> None:
    """Fails if a mismatched reward returns before its asynchronously released fixture is ready."""
    task_id = "task-id"
    runner = ChromeCuaRunner(
        gateway_url="http://127.0.0.1:18000/",
        fixture_health_url="http://127.0.0.1:53101/health",
        timeout_seconds=17.0,
        output_dir=tmp_path,
        transport=RecordingTransport(
            [_action_response(10, task_id), _reward_response(10, task_id, 0.0)]
        ),
        health_transport=RecordingFixtureHealthTransport(
            [
                {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
                {"slot_states": {"idle": 0, "resetting": 1, "busy": 0, "broken": 0}},
                {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
            ]
        ),
        health_poll_interval_seconds=0.01,
        sleep=lambda _seconds: None,
    )

    with pytest.raises(RewardMismatchError, match="expected reward 1.0, got 0.0"):
        runner.run(
            plan=ValidationPlan(
                cases=[ActionCase(name="mismatch", task_id=task_id, session_id=10, expected_reward=1.0)]
            ),
            provenance=_provenance(),
        )

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["cases"][0]["release"]["status"] == "ready"
    assert len(manifest["cases"][0]["release"]["polls"]) == 2


def test_runner_requires_post_reward_release_transition_before_accepting_idle(tmp_path: Path) -> None:
    """Fails if stale idle health after reward can start the next fresh CUA session."""
    task_id = "task-id"
    runner = ChromeCuaRunner(
        gateway_url="http://127.0.0.1:18000/",
        fixture_health_url="http://127.0.0.1:53101/health",
        timeout_seconds=17.0,
        output_dir=tmp_path,
        transport=RecordingTransport(
            [
                _action_response(10, task_id),
                _reward_response(10, task_id, 0.0),
                _action_response(11, task_id),
                _reward_response(11, task_id, 0.0),
            ]
        ),
        health_transport=RecordingFixtureHealthTransport(
            [
                {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
                {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
                {"slot_states": {"idle": 0, "resetting": 1, "busy": 0, "broken": 0}},
                {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
                {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
                {"slot_states": {"idle": 0, "resetting": 0, "busy": 1, "broken": 0}},
                {"slot_states": {"idle": 1, "resetting": 0, "busy": 0, "broken": 0}},
            ]
        ),
        health_poll_interval_seconds=0.01,
        sleep=lambda _seconds: None,
    )

    manifest_path = runner.run(
        plan=ValidationPlan(
            cases=[
                ActionCase(name="first", task_id=task_id, session_id=10, expected_reward=0.0),
                ActionCase(name="second", task_id=task_id, session_id=11, expected_reward=0.0),
            ]
        ),
        provenance=_provenance(),
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [
        poll["slot_states"] for poll in manifest["cases"][0]["release"]["polls"]
    ] == [
        {"idle": 1, "resetting": 0, "busy": 0, "broken": 0},
        {"idle": 0, "resetting": 1, "busy": 0, "broken": 0},
        {"idle": 1, "resetting": 0, "busy": 0, "broken": 0},
    ]


@pytest.mark.parametrize(
    ("terminal_action", "expected_reward"),
    [("DONE", 0.0), ("FAIL", 1.0)],
)
def test_runner_records_infeasible_terminal_action_controls(
    tmp_path: Path,
    terminal_action: str,
    expected_reward: float,
) -> None:
    """Fails if terminal action controls no longer preserve their expected reward semantics."""
    task_id = "3720f614-37fd-4d04-8a6b-76f54f8c222d"
    session_id = 3720 if terminal_action == "DONE" else 3721
    transport = RecordingTransport(
        [
            _action_response(session_id, task_id),
            _action_response(session_id, task_id),
            _reward_response(session_id, task_id, expected_reward),
        ]
    )
    plan = ValidationPlan(
        cases=[
            ActionCase(
                name=terminal_action.lower(),
                task_id=task_id,
                session_id=session_id,
                expected_reward=expected_reward,
                actions=[[{"action_type": terminal_action}]],
            )
        ]
    )

    manifest_path = ChromeCuaRunner(
        gateway_url="http://127.0.0.1:18000/",
        fixture_health_url="http://127.0.0.1:53101/health",
        timeout_seconds=17.0,
        output_dir=tmp_path,
        transport=transport,
        health_transport=AlwaysReadyFixtureHealthTransport(),
    ).run(plan=plan, provenance=_provenance())

    assert transport.requests[1]["actions"] == [{"action_type": terminal_action}]
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["run_status"] == "passed"


def test_runner_preserves_gateway_error_response_in_manifest(tmp_path: Path) -> None:
    """Fails if a gateway error loses its original payload while the runner raises."""
    task_id = "task-id"
    transport = RecordingTransport(
        [
            {
                "status": "error",
                "session_id": 9,
                "task_id": task_id,
                "error_type": "UPSTREAM",
                "message": "fixture unavailable",
            }
        ]
    )
    runner = ChromeCuaRunner(
        gateway_url="http://127.0.0.1:18000/",
        fixture_health_url="http://127.0.0.1:53101/health",
        timeout_seconds=17.0,
        output_dir=tmp_path,
        transport=transport,
        health_transport=AlwaysReadyFixtureHealthTransport(),
    )

    with pytest.raises(GatewayResponseError, match="fixture unavailable"):
        runner.run(
            plan=ValidationPlan(
                cases=[ActionCase(name="initial", task_id=task_id, session_id=9, expected_reward=0.0)]
            ),
            provenance=_provenance(),
        )

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_status"] == "failed"
    assert manifest["cases"][0]["events"][0]["response"] == {
        "status": "error",
        "session_id": 9,
        "task_id": task_id,
        "error_type": "UPSTREAM",
        "message": "fixture unavailable",
    }


def test_accepted_provenance_requires_all_evidence_fields() -> None:
    """Fails if a manifest can assert accepted image provenance without audit evidence."""
    with pytest.raises(ValidationError, match="accepted provenance requires"):
        ChromeProvenance.model_validate({**_CANONICAL_PROVENANCE, "acceptance_state": "accepted"})


def test_canonical_docker_provenance_is_accepted_and_preserved() -> None:
    """Fails if the runner requires a hand-translated provenance input instead of the Docker record."""
    provenance = ChromeProvenance.model_validate(_CANONICAL_PROVENANCE)

    assert provenance.model_dump(mode="json") == _CANONICAL_PROVENANCE


def test_accepted_provenance_rejects_pending_evidence_values() -> None:
    """Fails if a pending build record can be mislabeled as accepted provenance."""
    with pytest.raises(ValidationError, match="accepted provenance requires"):
        ChromeProvenance.model_validate(
            {
                **_CANONICAL_PROVENANCE,
                "acceptance_state": "accepted",
                "functional_compatibility_status": "passed",
            }
        )


def test_accepted_provenance_rejects_blank_final_fixture_digest() -> None:
    """Fails if a blank final image digest can satisfy the accepted-provenance gate."""
    with pytest.raises(ValidationError, match="accepted provenance requires"):
        ChromeProvenance.model_validate(
            {
                **_CANONICAL_PROVENANCE,
                "acceptance_state": "accepted",
                "functional_compatibility_status": "passed",
                "final_base_image_digest": "sha256:base",
                "final_fixture_image_digest": "",
                "final_profile_template_sha256": "sha256:profile",
            }
        )


def test_default_plan_contains_password_manager_and_infeasible_controls() -> None:
    """Fails if the executable and terminal-control CUA scenarios drift from their protocol plan."""
    plan = chrome_cua.default_validation_plan(base_session_id=1208655001)

    assert [(case.name, case.session_id, case.expected_reward) for case in plan.cases] == [
        ("password-manager-initial", 1208655001, 0.0),
        ("password-manager-action", 1208655002, 1.0),
        ("infeasible-done", 1208655003, 0.0),
        ("infeasible-fail", 1208655004, 1.0),
    ]
    assert plan.cases[1].actions == [
        [{"action_type": "HOTKEY", "keys": ["Control", "l"]}],
        [{"action_type": "TYPING", "text": "chrome://password-manager/passwords"}],
        [{"action_type": "PRESS", "key": "Enter"}],
        [{"action_type": "WAIT"}],
    ]
    assert plan.cases[2].actions == [[{"action_type": "DONE"}]]
    assert plan.cases[3].actions == [[{"action_type": "FAIL"}]]


def test_cli_exposes_local_runtime_and_evidence_inputs() -> None:
    """Fails if operators cannot supply the runtime endpoint, timeout, plan, and provenance."""
    script = Path(__file__).parents[2] / "scripts" / "validate_chrome_cua.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "--gateway-url" in completed.stdout
    assert "--fixture-health-url" in completed.stdout
    assert "--timeout-seconds" in completed.stdout
    assert "--plan" in completed.stdout
    assert "--provenance" in completed.stdout


def test_cli_accepts_the_canonical_docker_provenance_file(tmp_path: Path) -> None:
    """Fails if the CLI needs a hand-translated provenance JSON before it can parse Docker's record."""
    provenance_path = tmp_path / "chrome-provenance.json"
    provenance_path.write_text(json.dumps(_CANONICAL_PROVENANCE), encoding="utf-8")
    script = Path(__file__).parents[2] / "scripts" / "validate_chrome_cua.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--gateway-url",
            "http://127.0.0.1:18000/",
            "--fixture-health-url",
            "http://127.0.0.1:53101/health",
            "--timeout-seconds",
            "0",
            "--output-dir",
            str(tmp_path / "output"),
            "--provenance",
            str(provenance_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "timeout_seconds must be > 0" in completed.stderr
    assert "ValidationError" not in completed.stderr
