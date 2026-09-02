from __future__ import annotations

import base64
import hashlib
import importlib
import importlib.util
from types import ModuleType

import pytest
from pydantic import ValidationError
from surfgym_contracts.protocol import gateway_to_agent, gateway_to_upstream
from surfgym_contracts.protocol.agent_to_gateway import (
    AgentRequestAdapter,
    RewardRequest,
    StartRequest,
)

MAX_ARTIFACT_BYTES = 4 * 1024 * 1024


def _artifact_contract() -> ModuleType:
    module_name = "surfgym_contracts.protocol.artifact"
    assert importlib.util.find_spec(module_name) is not None, (
        "the shared artifact contract module must exist"
    )
    return importlib.import_module(module_name)


def _valid_payload() -> dict[str, object]:
    raw = b"artifact"
    return {
        "path": "Desktop/out.txt",
        "mime_type": "text/plain",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
        "encoding": "base64",
        "data": base64.b64encode(raw).decode("ascii"),
    }


def test_legacy_reward_request_and_response_remain_artifact_free() -> None:
    request = AgentRequestAdapter.validate_python(
        {"op": "reward", "session_id": 1, "task_id": "task"}
    )
    response = gateway_to_agent.RewardResponse(
        session_id=1,
        task_id="task",
        reward=1.0,
    )

    assert type(request) is RewardRequest
    assert request.artifacts is None
    assert response.model_dump(mode="json") == {
        "session_id": 1,
        "task_id": "task",
        "status": "ok",
        "reward": 1.0,
        "image": None,
    }


def test_non_reward_requests_preserve_existing_extra_field_behavior() -> None:
    request = AgentRequestAdapter.validate_python(
        {
            "op": "start",
            "session_id": 1,
            "task_id": "task",
            "legacy_extra": "ignored",
        }
    )

    assert type(request) is StartRequest
    assert "legacy_extra" not in request.model_dump()


@pytest.mark.parametrize(
    "artifacts",
    [
        None,
        [],
        [{"path": "Desktop/out.txt", "max_bytes": True}],
        [{"path": "Desktop/out.txt", "max_bytes": 1.5}],
        [{"path": "Desktop/out.txt", "max_bytes": "1"}],
        [{"path": "Desktop/out.txt", "max_bytes": 0}],
        [{"path": "Desktop/out.txt", "max_bytes": MAX_ARTIFACT_BYTES + 1}],
        [{"path": f"Desktop/{index}.txt", "max_bytes": 1} for index in range(5)],
        [{"path": "Desktop/out.txt", "max_bytes": 1, "extra": True}],
    ],
)
def test_present_reward_artifacts_reject_noncanonical_shapes(
    artifacts: object,
) -> None:
    with pytest.raises(ValidationError):
        AgentRequestAdapter.validate_python(
            {
                "op": "reward",
                "session_id": 1,
                "task_id": "task",
                "artifacts": artifacts,
            }
        )


def test_reward_request_rejects_extra_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        AgentRequestAdapter.validate_python(
            {
                "op": "reward",
                "session_id": 1,
                "task_id": "task",
                "artifacts": [{"path": "Desktop/out.txt", "max_bytes": 1}],
                "extra": True,
            }
        )


def test_reward_request_accepts_one_to_four_artifacts_with_four_mib_total() -> None:
    request = AgentRequestAdapter.validate_python(
        {
            "op": "reward",
            "session_id": 1,
            "task_id": "task",
            "artifacts": [
                {"path": f"Desktop/{index}.bin", "max_bytes": 1024 * 1024}
                for index in range(4)
            ],
        }
    )

    assert isinstance(request, RewardRequest)
    assert request.artifacts is not None
    assert [artifact.path for artifact in request.artifacts] == [
        "Desktop/0.bin",
        "Desktop/1.bin",
        "Desktop/2.bin",
        "Desktop/3.bin",
    ]


def test_reward_request_rejects_declared_aggregate_over_four_mib() -> None:
    with pytest.raises(ValidationError, match="aggregate"):
        AgentRequestAdapter.validate_python(
            {
                "op": "reward",
                "session_id": 1,
                "task_id": "task",
                "artifacts": [
                    {"path": "Desktop/a.bin", "max_bytes": 2 * 1024 * 1024},
                    {"path": "Desktop/b.bin", "max_bytes": 2 * 1024 * 1024 + 1},
                ],
            }
        )


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/Desktop/out.txt",
        "Desktop/out.txt/",
        "Desktop//out.txt",
        r"Desktop\out.txt",
        "C:/Desktop/out.txt",
        ".",
        "..",
        "Desktop/./out.txt",
        "Desktop/../out.txt",
        "Desktop/\x00out.txt",
        "Desktop/\x1fout.txt",
        "Desktop/\x7fout.txt",
        "/".join(["a"] * 65),
        "Desktop/" + "a" * 256,
        "a/" + "b" * 511,
        "Desktop/" + "한" * 169,
    ],
)
def test_artifact_spec_rejects_noncanonical_relative_posix_paths(path: str) -> None:
    artifact = _artifact_contract()

    with pytest.raises(ValidationError):
        artifact.ArtifactSpec(path=path, max_bytes=1)


def test_artifact_spec_accepts_utf8_and_component_boundaries() -> None:
    artifact = _artifact_contract()
    sixty_four_components = "/".join(["a"] * 64)
    utf8_path = f"{'한' * 84}/{'한' * 84}"

    assert artifact.ArtifactSpec(path=sixty_four_components, max_bytes=1).path == (
        sixty_four_components
    )
    assert artifact.ArtifactSpec(path=utf8_path, max_bytes=1).path == utf8_path


@pytest.mark.parametrize(
    "updates",
    [
        {"extra": True},
        {"path": "Desktop/../out.txt"},
        {"mime_type": "TEXT/PLAIN"},
        {"mime_type": "text/plain; charset=utf-8"},
        {"mime_type": "text /plain"},
        {"mime_type": "text/plain/extra"},
        {"mime_type": "t\u00e9xt/plain"},
        {"mime_type": "a/" + "b" * 254},
        {"encoding": "hex"},
        {"data": "%%%"},
        {"data": "AB==", "size": 1, "sha256": hashlib.sha256(b"\x00").hexdigest()},
        {"size": 9},
        {"sha256": "0" * 64},
    ],
)
def test_artifact_payload_rejects_noncanonical_or_inconsistent_content(
    updates: dict[str, object],
) -> None:
    artifact = _artifact_contract()
    payload = _valid_payload()
    payload.update(updates)

    with pytest.raises(ValidationError):
        artifact.ArtifactPayload.model_validate(payload)


def test_artifact_payload_accepts_exact_canonical_content() -> None:
    artifact = _artifact_contract()

    payload = artifact.ArtifactPayload.model_validate(_valid_payload())

    assert payload.model_dump(mode="json") == _valid_payload()


def test_gateway_to_upstream_artifact_request_is_exact_and_nested() -> None:
    artifact = _artifact_contract()
    request_type = getattr(gateway_to_upstream, "ArtifactRequest", None)
    assert request_type is not None, "the instance artifact request contract must exist"
    spec = artifact.ArtifactSpec(path="Desktop/out.txt", max_bytes=128)

    request = request_type(artifact=spec)

    assert request.model_dump(mode="json") == {
        "artifact": {"path": "Desktop/out.txt", "max_bytes": 128}
    }
    with pytest.raises(ValidationError):
        request_type(artifact=spec, extra=True)


def test_reward_bundle_response_round_trips_without_changing_legacy_union() -> None:
    artifact = _artifact_contract()
    bundle_type = getattr(gateway_to_agent, "RewardBundleResponse", None)
    assert bundle_type is not None, "the reward bundle response contract must exist"
    payload = artifact.ArtifactPayload.model_validate(_valid_payload())

    bundle = bundle_type(
        session_id=1,
        task_id="task",
        reward=1.0,
        artifacts=[payload],
    )
    parsed_bundle = gateway_to_agent.ResponseAdapter.validate_python(
        bundle.model_dump(mode="json")
    )
    parsed_legacy = gateway_to_agent.ResponseAdapter.validate_python(
        gateway_to_agent.RewardResponse(
            session_id=1,
            task_id="task",
            reward=1.0,
        ).model_dump(mode="json")
    )

    assert type(parsed_bundle) is bundle_type
    assert parsed_bundle.artifacts == [payload]
    assert type(parsed_legacy) is gateway_to_agent.RewardResponse
