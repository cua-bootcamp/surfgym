import argparse
import copy
import json
import sqlite3
import sys
from dataclasses import replace

import pytest
import surfgym_task.cua.import_task as import_task_module
from surfgym_contracts.task import CuaEvaluation
from surfgym_runtime.support.cua_evaluator import CuaSnapshot, evaluate_cua_reward
from surfgym_task.cua.bundle_store import Bundle
from surfgym_task.cua.import_task import (
    _episode_pairs,
    import_direct_web_task,
    parse_args,
    write_host_states,
    write_task_assets,
)
from surfgym_task.web import WEB_STATE_RESET_HOOK

CANARY_TASK_ID = "133a8676-fa79-518c-b000-5d51d4791db2"


def _instagram_bundle() -> Bundle:
    return Bundle(
        task_id=CANARY_TASK_ID,
        task_json=json.dumps(
            {
                "id": CANARY_TASK_ID,
                "instruction": "I need to update my username to 'alex_photo_sf'. Can you do that?",
                "app_type": "instagram_mock",
            }
        ),
        initial_setup="""
import requests
requests.post(
    '__CUA_GYM_INSTAGRAM_URL__/post?sid=source-sid',
    json={
        'action': 'set',
        'state': {
            'currentUserId': 'user_admin',
            'users': {
                'user_admin': {
                    'id': 'user_admin',
                    'username': 'alex_morgan',
                    'name': 'Alex Morgan',
                    'bio': 'Photographer',
                }
            },
        },
    },
)
""",
        reward="""
import requests
with open('/tmp/task_web_sid') as sid_file:
    sid = sid_file.read().strip()
data = requests.get(f'__CUA_GYM_INSTAGRAM_URL__/go?sid={sid}').json()
admin = data['current_state']['users']['user_admin']
username_correct = admin['username'] == 'alex_photo_sf'
profile_intact = admin['name'] == 'Alex Morgan' and admin['bio'] == 'Photographer'
print(f"REWARD: {1.0 if username_correct and profile_intact else 0.0}")
""",
    )


def test_instagram_username_canary_import_preserves_evaluator_contract(tmp_path):
    imported = import_direct_web_task(
        _instagram_bundle(), app_url="http://127.0.0.1:8052/"
    )
    task_dir = write_task_assets(imported, tmp_path)
    state_root = write_host_states(imported, tmp_path)

    assert imported.app_key == "INSTAGRAM"
    assert imported.task.task_id == CANARY_TASK_ID
    assert imported.task.website[0].url == (
        f"http://127.0.0.1:8052/?sid={CANARY_TASK_ID}"
    )
    assert isinstance(imported.task.evaluation, CuaEvaluation)
    assert imported.task.evaluation.source_task_id == CANARY_TASK_ID
    assert imported.task.evaluation.states[0].sid == CANARY_TASK_ID
    assert imported.task.lifecycle_hooks.release == [WEB_STATE_RESET_HOOK]
    assert imported.task.evaluation.states[0].current_state_key == (
        f"instagram_mock_state_{CANARY_TASK_ID}"
    )
    assert imported.task.evaluation.states[0].initial_state_key == (
        f"instagram_mock_initialState_{CANARY_TASK_ID}"
    )
    assert imported.task.evaluation.states[0].app_base == "http://127.0.0.1:8052"
    assert "__CUA_GYM_INSTAGRAM_URL__" not in imported.task.evaluation.reward_script
    assert "http://127.0.0.1:8052/go?sid={sid}" in imported.task.evaluation.reward_script
    assert "alex_photo_sf" in imported.task.evaluation.reward_script
    assert "Alex Morgan" in imported.task.evaluation.reward_script
    assert "Photographer" in imported.task.evaluation.reward_script

    stored = json.loads(
        (task_dir / "initial_states" / "INSTAGRAM" / f"{CANARY_TASK_ID}.json").read_text()
    )
    admin = stored["stored_state"]["users"]["user_admin"]
    assert stored["sid"] == CANARY_TASK_ID
    assert admin == {
        "id": "user_admin",
        "username": "alex_morgan",
        "name": "Alex Morgan",
        "bio": "Photographer",
    }
    assert json.loads(
        (state_root / "INSTAGRAM" / f"{CANARY_TASK_ID}.json").read_text()
    ) == stored

    initial_state = stored["stored_state"]
    success_state = copy.deepcopy(initial_state)
    success_state["users"]["user_admin"]["username"] = "alex_photo_sf"
    initial_result = evaluate_cua_reward(
        imported.task.evaluation.reward_script,
        source_task_id=CANARY_TASK_ID,
        sid=CANARY_TASK_ID,
        snapshots={
            "http://127.0.0.1:8052": CuaSnapshot(
                initial_state=initial_state,
                current_state=initial_state,
            )
        },
        timeout=5.0,
    )
    success_result = evaluate_cua_reward(
        imported.task.evaluation.reward_script,
        source_task_id=CANARY_TASK_ID,
        sid=CANARY_TASK_ID,
        snapshots={
            "http://127.0.0.1:8052": CuaSnapshot(
                initial_state=initial_state,
                current_state=success_state,
            )
        },
        timeout=5.0,
    )
    assert initial_result.reward == 0.0
    assert success_result.reward == 1.0


def test_instagram_import_supports_run_scoped_episode_sid(tmp_path):
    episode_sid = "instagram-canary-run-01"
    imported = import_direct_web_task(
        _instagram_bundle(),
        app_url="http://127.0.0.1:8052/",
        sid=episode_sid,
    )
    task_dir = write_task_assets(imported, tmp_path)
    state_root = write_host_states(imported, tmp_path)

    assert imported.task.task_id == episode_sid
    assert imported.task.evaluation.source_task_id == CANARY_TASK_ID
    assert imported.task.evaluation.states[0].sid == episode_sid
    assert imported.task.website[0].url == (
        f"http://127.0.0.1:8052/?sid={episode_sid}"
    )
    assert imported.task.evaluation.states[0].current_state_key == (
        f"instagram_mock_state_{episode_sid}"
    )
    assert imported.task.evaluation.states[0].initial_state_key == (
        f"instagram_mock_initialState_{episode_sid}"
    )
    assert imported.task.lifecycle_hooks.release == [WEB_STATE_RESET_HOOK]

    task_state_path = (
        task_dir / "initial_states" / "INSTAGRAM" / f"{episode_sid}.json"
    )
    host_state_path = state_root / "INSTAGRAM" / f"{episode_sid}.json"
    stored = json.loads(task_state_path.read_text(encoding="utf-8"))
    assert stored["sid"] == episode_sid
    assert json.loads(host_state_path.read_text(encoding="utf-8")) == stored
    assert not (
        task_dir / "initial_states" / "INSTAGRAM" / f"{CANARY_TASK_ID}.json"
    ).exists()


def test_import_rejects_recorded_setup_from_another_source():
    bundle = _instagram_bundle()
    recorded_setup = replace(import_task_module.record(bundle), task_id="wrong-source")

    with pytest.raises(ValueError, match="does not match bundle"):
        import_direct_web_task(
            bundle,
            app_url="http://127.0.0.1:8052/",
            sid="instagram-run-01",
            recorded_setup=recorded_setup,
        )


def test_episode_pairs_reject_duplicate_source_and_runtime_ids():
    with pytest.raises(ValueError, match="count must match"):
        _episode_pairs([CANARY_TASK_ID, CANARY_TASK_ID], ["instagram-run-01"])
    with pytest.raises(ValueError, match="--task-id values must be unique"):
        _episode_pairs(
            [CANARY_TASK_ID, CANARY_TASK_ID],
            ["instagram-run-01", "instagram-run-02"],
        )
    assert _episode_pairs(
        [CANARY_TASK_ID, "another-source-task"],
        ["instagram-run-01", "other-app-run-01"],
    ) == [
        (CANARY_TASK_ID, "instagram-run-01"),
        ("another-source-task", "other-app-run-01"),
    ]
    with pytest.raises(ValueError, match="derived runtime task IDs must be unique"):
        _episode_pairs(
            [CANARY_TASK_ID, "another-source-task"],
            ["instagram-run-01", "instagram-run-01"],
        )


@pytest.mark.parametrize(
    "episode_sid",
    ["CON", "con.json", "NUL", "bad:name", "with space", "trailing."],
)
def test_explicit_episode_sid_must_be_windows_portable(episode_sid, tmp_path):
    with pytest.raises(ValueError, match="invalid episode SID"):
        _episode_pairs([CANARY_TASK_ID], [episode_sid])
    with pytest.raises(ValueError, match="invalid episode SID"):
        import_task_module.write_states(
            import_task_module.record(_instagram_bundle()),
            tmp_path,
            sid=episode_sid,
        )


def test_import_cli_parses_aligned_episode_sids(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_task",
            "--archive",
            "bundles.zip",
            "--task-id",
            CANARY_TASK_ID,
            "another-source-task",
            "--episode-sid",
            "instagram-run-01",
            "instagram-run-02",
            "--ports-file",
            "ports.json",
            "--output-dir",
            "staging",
        ],
    )

    args = parse_args()

    assert args.task_id == [CANARY_TASK_ID, "another-source-task"]
    assert args.episode_sid == ["instagram-run-01", "instagram-run-02"]


def test_cli_imports_normal_two_task_batch(tmp_path, monkeypatch):
    ports_file = tmp_path / "ports.json"
    ports_file.write_text(
        json.dumps({"INSTAGRAM": "http://127.0.0.1:8052"}), encoding="utf-8"
    )
    output_dir = tmp_path / "staging"
    second_task_id = "another-instagram-source-task"
    second_bundle = replace(
        _instagram_bundle(),
        task_id=second_task_id,
        task_json=json.dumps(
            {
                "id": second_task_id,
                "instruction": "Update another profile.",
                "app_type": "instagram_mock",
            }
        ),
    )
    args = argparse.Namespace(
        archive=tmp_path / "bundles.zip",
        task_id=[CANARY_TASK_ID, second_task_id],
        episode_sid=["instagram-run-01", "instagram-run-02"],
        ports_file=ports_file,
        output_dir=output_dir,
    )
    monkeypatch.setattr(import_task_module, "parse_args", lambda: args)
    monkeypatch.setattr(
        import_task_module,
        "read_bundles",
        lambda _archive, _task_ids: {
            CANARY_TASK_ID: _instagram_bundle(),
            second_task_id: second_bundle,
        },
    )
    real_record = import_task_module.record
    record_calls = 0

    def counting_record(bundle):
        nonlocal record_calls
        record_calls += 1
        return real_record(bundle)

    monkeypatch.setattr(import_task_module, "record", counting_record)

    import_task_module.main()

    assert record_calls == 2
    task_state_paths = [
        output_dir / sid / "initial_states" / "INSTAGRAM" / f"{sid}.json"
        for sid in ("instagram-run-01", "instagram-run-02")
    ]
    task_payloads = [
        json.loads(path.read_text(encoding="utf-8")) for path in task_state_paths
    ]
    for sid, task_state_path in zip(
        ("instagram-run-01", "instagram-run-02"), task_state_paths
    ):
        assert (
            output_dir / "initial_states" / "INSTAGRAM" / f"{sid}.json"
        ).read_bytes() == task_state_path.read_bytes()
    stored_state_bytes = [
        json.dumps(
            payload["stored_state"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        for payload in task_payloads
    ]
    assert stored_state_bytes[0] == stored_state_bytes[1]

    tasks_db = output_dir / "tasks.sqlite3"

    with sqlite3.connect(tasks_db) as connection:
        rows = connection.execute(
            "SELECT task_id, payload FROM tasks ORDER BY task_id"
        ).fetchall()

    assert [task_id for task_id, _ in rows] == [
        "instagram-run-01",
        "instagram-run-02",
    ]
    assert {
        json.loads(payload)["evaluation"]["source_task_id"] for _, payload in rows
    } == {CANARY_TASK_ID, second_task_id}


def test_late_bundle_failure_does_not_mutate_existing_output(tmp_path, monkeypatch):
    ports_file = tmp_path / "ports.json"
    ports_file.write_text(
        json.dumps({"INSTAGRAM": "http://127.0.0.1:8052"}), encoding="utf-8"
    )
    output_dir = tmp_path / "staging"
    sentinel_paths = {
        output_dir / "tasks.sqlite3": b"existing-db",
        output_dir / "initial_states" / "INSTAGRAM" / "keep.json": b"existing-state",
        output_dir / "existing-task" / "task.json": b"existing-task",
    }
    for path, contents in sentinel_paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)

    invalid_task_id = "invalid-second-bundle"
    invalid_bundle = replace(
        _instagram_bundle(), task_id=invalid_task_id, reward=None
    )
    args = argparse.Namespace(
        archive=tmp_path / "bundles.zip",
        task_id=[CANARY_TASK_ID, invalid_task_id],
        episode_sid=["instagram-run-01", "instagram-run-02"],
        ports_file=ports_file,
        output_dir=output_dir,
    )
    monkeypatch.setattr(import_task_module, "parse_args", lambda: args)
    monkeypatch.setattr(
        import_task_module,
        "read_bundles",
        lambda _archive, _task_ids: {
            CANARY_TASK_ID: _instagram_bundle(),
            invalid_task_id: invalid_bundle,
        },
    )

    with pytest.raises(ValueError, match="invalid-second-bundle is incomplete"):
        import_task_module.main()

    assert {path: path.read_bytes() for path in sentinel_paths} == sentinel_paths
    assert sorted(path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*")) == [
        "existing-task",
        "existing-task/task.json",
        "initial_states",
        "initial_states/INSTAGRAM",
        "initial_states/INSTAGRAM/keep.json",
        "tasks.sqlite3",
    ]


def test_valid_batch_fails_closed_when_output_is_nonempty(tmp_path, monkeypatch):
    ports_file = tmp_path / "ports.json"
    ports_file.write_text(
        json.dumps({"INSTAGRAM": "http://127.0.0.1:8052"}), encoding="utf-8"
    )
    output_dir = tmp_path / "staging"
    output_dir.mkdir()
    sentinel = output_dir / "keep.txt"
    sentinel.write_text("unchanged", encoding="utf-8")
    args = argparse.Namespace(
        archive=tmp_path / "bundles.zip",
        task_id=[CANARY_TASK_ID],
        episode_sid=["instagram-run-01"],
        ports_file=ports_file,
        output_dir=output_dir,
    )
    monkeypatch.setattr(import_task_module, "parse_args", lambda: args)
    monkeypatch.setattr(
        import_task_module,
        "read_bundles",
        lambda _archive, _task_ids: {CANARY_TASK_ID: _instagram_bundle()},
    )

    with pytest.raises(SystemExit, match="output directory must be empty"):
        import_task_module.main()

    assert list(output_dir.iterdir()) == [sentinel]
    assert sentinel.read_text(encoding="utf-8") == "unchanged"
