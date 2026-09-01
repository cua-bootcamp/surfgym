import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[3]
REFERENCE_VERIFIER = (
    REPO_ROOT / "scripts" / "cua_hub_deploy" / ("verify_state_seed_reference_replay.mjs")
)
TASK_DB_VERIFIER = REPO_ROOT / "scripts" / "cua_hub_deploy" / ("verify_state_seed_task_db.py")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_task_db_verifier():
    spec = importlib.util.spec_from_file_location("verify_state_seed_task_db", TASK_DB_VERIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reference_fixture(tmp_path: Path, state_path: str) -> dict[str, Path]:
    task_id = "task-1"
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    state = evidence_root / "state.json"
    _write_json(state, {"done": True})
    seed = tmp_path / "seeds" / "seed.json"
    _write_json(
        seed,
        {
            "states": [
                [],
                [{"spec": {"script": "state.done === true"}, "value": True}],
            ]
        },
    )
    replay_map = evidence_root / "map.json"
    _write_json(replay_map, {"tasks": [{"task_id": task_id, "state_path": state_path}]})
    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {
            "evidence": {"reference_replay_map_sha256": _sha256(replay_map)},
            "counts": {"tasks": 1, "terminal_criteria": 1},
            "tasks": [{"source_task_id": task_id, "seed": seed.name}],
        },
    )
    return {
        "evidence_root": evidence_root,
        "manifest": manifest,
        "map": replay_map,
        "seeds": seed.parent,
        "report": tmp_path / "report.json",
    }


def _run_reference_verifier(fixture: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the reference replay verifier")
    return subprocess.run(
        [
            node,
            str(REFERENCE_VERIFIER),
            "--manifest",
            str(fixture["manifest"]),
            "--map",
            str(fixture["map"]),
            "--evidence-root",
            str(fixture["evidence_root"]),
            "--seeds-dir",
            str(fixture["seeds"]),
            "--report",
            str(fixture["report"]),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_reference_replay_accepts_pinned_map_inside_evidence_root(tmp_path: Path) -> None:
    fixture = _reference_fixture(tmp_path, "state.json")

    completed = _run_reference_verifier(fixture)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(fixture["report"].read_text(encoding="utf-8"))["status"] == "PASS"


def test_reference_replay_rejects_substituted_map(tmp_path: Path) -> None:
    fixture = _reference_fixture(tmp_path, "state.json")
    fixture["map"].write_text(
        fixture["map"].read_text(encoding="utf-8") + " ",
        encoding="utf-8",
    )

    completed = _run_reference_verifier(fixture)

    assert completed.returncode != 0
    assert "reference replay map SHA-256 mismatch" in completed.stderr


def test_reference_replay_rejects_map_outside_evidence_root(tmp_path: Path) -> None:
    fixture = _reference_fixture(tmp_path, "state.json")
    outside_map = tmp_path / "outside-map.json"
    outside_map.write_bytes(fixture["map"].read_bytes())
    fixture["map"] = outside_map

    completed = _run_reference_verifier(fixture)

    assert completed.returncode != 0
    assert "reference replay map is outside evidence root" in completed.stderr


@pytest.mark.parametrize("path_kind", ["parent", "absolute"])
def test_reference_replay_rejects_state_outside_evidence_root(
    tmp_path: Path,
    path_kind: str,
) -> None:
    outside = tmp_path / "outside.json"
    _write_json(outside, {"done": True})
    state_path = "../outside.json" if path_kind == "parent" else str(outside.resolve())
    fixture = _reference_fixture(tmp_path, state_path)

    completed = _run_reference_verifier(fixture)

    assert completed.returncode != 0
    assert "state evidence path" in completed.stderr


def test_task_db_verifier_accepts_pinned_report_inside_evidence_root(
    tmp_path: Path,
) -> None:
    verifier = _load_task_db_verifier()
    evidence_root = tmp_path / "evidence"
    report = evidence_root / "report.json"
    _write_json(report, {"status": "PASS"})
    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {"evidence": {"reference_replay_report_sha256": _sha256(report)}},
    )

    resolved = verifier._verify_pinned_reference_report(manifest, report, evidence_root)

    assert resolved == report.resolve()


def test_task_db_verifier_rejects_substituted_report(tmp_path: Path) -> None:
    verifier = _load_task_db_verifier()
    evidence_root = tmp_path / "evidence"
    report = evidence_root / "report.json"
    _write_json(report, {"status": "PASS"})
    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {"evidence": {"reference_replay_report_sha256": _sha256(report)}},
    )
    report.write_text(report.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(ValueError, match="reference replay report SHA-256 mismatch"):
        verifier._verify_pinned_reference_report(manifest, report, evidence_root)


def test_task_db_verifier_rejects_report_outside_evidence_root(tmp_path: Path) -> None:
    verifier = _load_task_db_verifier()
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    report = tmp_path / "outside.json"
    _write_json(report, {"status": "PASS"})
    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {"evidence": {"reference_replay_report_sha256": _sha256(report)}},
    )

    with pytest.raises(ValueError, match="outside evidence root"):
        verifier._verify_pinned_reference_report(manifest, report, evidence_root)
