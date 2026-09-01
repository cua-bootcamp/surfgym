import json
from pathlib import Path
from runpy import run_path

from surfgym_task.web import WEB_STATE_RESET_HOOK

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VERIFY_MODULE = run_path(
    str(_REPO_ROOT / "scripts/cua_hub_deploy/verify_imported_tasks.py")
)
verify_imported_tasks = _VERIFY_MODULE["verify_imported_tasks"]


def _write_imported_task(
    root: Path,
    *,
    done: bool,
    source_task_id: str = "task-1",
    episode_sid: str | None = None,
    include_release_hook: bool = True,
) -> Path:
    task_id = source_task_id if episode_sid is None else episode_sid
    task_dir = root / task_id
    app_base = "http://127.0.0.1:8999"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "instruction": "Mark the item done.",
                "website": [{"url": f"{app_base}/?sid={task_id}"}],
                "evaluation": {
                    "mode": "cua",
                    "source_task_id": source_task_id,
                    "reward_script": (
                        "import requests\n"
                        f"state = requests.get('{app_base}/go?sid={{{'sid'}}}').json()\n"
                        "print(f\"REWARD: {1.0 if state['current_state']['done'] else 0.0}\")\n"
                    ),
                    "states": [
                        {
                            "app_base": app_base,
                            "sid": task_id,
                            "current_state_key": f"instagram_mock_state_{task_id}",
                            "initial_state_key": f"instagram_mock_initialState_{task_id}",
                        }
                    ],
                },
                "lifecycle_hooks": {
                    "release": (
                        [WEB_STATE_RESET_HOOK.model_dump(mode="json")]
                        if include_release_hook
                        else []
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    state_dir = task_dir / "initial_states" / "INSTAGRAM"
    state_dir.mkdir(parents=True)
    state_text = json.dumps(
        {
            "sid": task_id,
            "has_custom_state": True,
            "stored_state": {"done": done},
        }
    )
    (state_dir / f"{task_id}.json").write_text(state_text, encoding="utf-8")
    host_state_dir = root / "initial_states" / "INSTAGRAM"
    host_state_dir.mkdir(parents=True, exist_ok=True)
    (host_state_dir / f"{task_id}.json").write_text(state_text, encoding="utf-8")
    return task_dir


def test_verify_imported_tasks_accepts_exact_zero_initial_reward(tmp_path: Path) -> None:
    _write_imported_task(tmp_path, done=False)

    report = verify_imported_tasks(tmp_path, timeout=5.0)

    assert report["status"] == "PASS"
    assert report["counts"] == {
        "discovered": 1,
        "evaluated": 1,
        "passed": 1,
        "errors": 0,
    }
    assert report["results"][0]["initial_reward"] == 0.0
    assert report["results"][0]["source_task_id"] == "task-1"
    assert report["results"][0]["episode_sid"] == "task-1"


def test_verify_imported_tasks_accepts_run_scoped_episode_sid(tmp_path: Path) -> None:
    _write_imported_task(
        tmp_path,
        done=False,
        source_task_id="source-task-uuid",
        episode_sid="instagram-run-02",
    )

    report = verify_imported_tasks(
        tmp_path,
        timeout=5.0,
        expected_sources={"instagram-run-02": "source-task-uuid"},
    )

    assert report["status"] == "PASS"
    assert report["results"][0]["task_id"] == "instagram-run-02"
    assert report["results"][0]["source_task_id"] == "source-task-uuid"
    assert report["results"][0]["episode_sid"] == "instagram-run-02"
    assert report["results"][0]["contract_checks"]["source_lineage"] == "PASS"
    assert (
        report["results"][0]["contract_checks"]["direct_web_release_hook"]
        == "PASS"
    )
    assert report["results"][0]["contract_checks"]["shared_host_state"] == "PASS"


def test_verify_imported_tasks_rejects_nonzero_initial_reward(tmp_path: Path) -> None:
    _write_imported_task(tmp_path, done=True)

    report = verify_imported_tasks(tmp_path, timeout=5.0)

    assert report["status"] == "FAIL"
    assert report["results"][0]["initial_reward"] == 1.0


def test_verify_imported_tasks_rejects_expected_source_lineage_mismatch(
    tmp_path: Path,
) -> None:
    _write_imported_task(
        tmp_path,
        done=False,
        source_task_id="source-task-uuid",
        episode_sid="instagram-run-04",
    )

    report = verify_imported_tasks(
        tmp_path,
        timeout=5.0,
        expected_sources={"instagram-run-04": "different-source-uuid"},
    )

    assert report["status"] == "FAIL"
    assert report["counts"]["errors"] == 1
    assert "does not match expected" in report["errors"][0]["error"]


def test_verify_imported_tasks_rejects_sid_and_key_contract_drift(tmp_path: Path) -> None:
    _write_imported_task(tmp_path, done=False)
    task_path = tmp_path / "task-1" / "task.json"
    task = json.loads(task_path.read_text(encoding="utf-8"))
    task["website"][0]["url"] = "http://127.0.0.1:8999/?sid=wrong"
    task["evaluation"]["states"][0]["current_state_key"] = "wrong-key"
    task_path.write_text(json.dumps(task), encoding="utf-8")

    report = verify_imported_tasks(tmp_path, timeout=5.0)

    assert report["status"] == "FAIL"
    assert report["counts"]["errors"] == 1
    assert "website URL does not match" in report["errors"][0]["error"]


def test_verify_imported_tasks_rejects_initial_state_envelope_sid_drift(
    tmp_path: Path,
) -> None:
    task_dir = _write_imported_task(
        tmp_path,
        done=False,
        source_task_id="source-task-uuid",
        episode_sid="instagram-run-03",
    )
    state_path = task_dir / "initial_states" / "INSTAGRAM" / "instagram-run-03.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["sid"] = "wrong"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    report = verify_imported_tasks(
        tmp_path,
        timeout=5.0,
        expected_sources={"instagram-run-03": "source-task-uuid"},
    )

    assert report["status"] == "FAIL"
    assert report["counts"]["errors"] == 1
    assert "initial-state envelope is not SID scoped" in report["errors"][0]["error"]


def test_verify_imported_tasks_rejects_missing_direct_web_release_hook(
    tmp_path: Path,
) -> None:
    _write_imported_task(tmp_path, done=False, include_release_hook=False)

    report = verify_imported_tasks(tmp_path, timeout=5.0)

    assert report["status"] == "FAIL"
    assert report["counts"]["errors"] == 1
    assert "exactly the direct-web release hook" in report["errors"][0]["error"]


def test_verify_imported_tasks_rejects_missing_shared_host_state(
    tmp_path: Path,
) -> None:
    _write_imported_task(tmp_path, done=False)
    (tmp_path / "initial_states" / "INSTAGRAM" / "task-1.json").unlink()

    report = verify_imported_tasks(tmp_path, timeout=5.0)

    assert report["status"] == "FAIL"
    assert report["counts"]["errors"] == 1
    assert "has no shared host state" in report["errors"][0]["error"]


def test_verify_imported_tasks_rejects_shared_host_state_drift(
    tmp_path: Path,
) -> None:
    _write_imported_task(tmp_path, done=False)
    host_state = tmp_path / "initial_states" / "INSTAGRAM" / "task-1.json"
    payload = json.loads(host_state.read_text(encoding="utf-8"))
    payload["stored_state"]["done"] = True
    host_state.write_text(json.dumps(payload), encoding="utf-8")

    report = verify_imported_tasks(tmp_path, timeout=5.0)

    assert report["status"] == "FAIL"
    assert report["counts"]["errors"] == 1
    assert "shared host state does not match" in report["errors"][0]["error"]
