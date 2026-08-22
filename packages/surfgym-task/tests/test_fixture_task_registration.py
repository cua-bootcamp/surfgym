import importlib
import json
from pathlib import Path

import pytest
from surfgym_task.main import _release_hooks
from surfgym_task.web import DOCKER_FIXTURE_RELEASE_HOOK, WEB_STATE_RESET_HOOK


def _fixture_task_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "task_id": "gimp-open-image",
        "hash": "gimp-open-image",
        "instruction": "Open the fixture image.",
        "website": {
            "base": "http://localhost:53001/gimp",
            "param": {"session": "fixture"},
        },
        "complexity": 1,
        "evaluation": {
            "operator": "and",
            "criteria": [{"target": "url", "match": "contains", "value": "/gimp"}],
        },
    }
    payload.update(overrides)
    return payload


def _write_task(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_fixture_tasks_registers_docker_release_without_web_reset(
    tmp_path: Path,
):
    web = importlib.import_module("surfgym_task.web")
    allocate_hook = {"timing": "after", "script": "window.fixture.allocate()"}
    _write_task(
        tmp_path / "fixture.json",
        _fixture_task_payload(lifecycle_hooks={"allocate": [allocate_hook]}),
    )

    task = web.load_fixture_tasks(tmp_path)[0]

    assert task.task_id == "gimp-open-image"
    assert task.website[0].url == "http://localhost:53001/gimp?session=fixture"
    assert task.lifecycle_hooks.release == [web.DOCKER_FIXTURE_RELEASE_HOOK]
    assert web.WEB_STATE_RESET_HOOK not in task.lifecycle_hooks.release
    assert [
        hook.model_dump(exclude_defaults=True) for hook in task.lifecycle_hooks.allocate
    ] == [allocate_hook]
    assert "hash" not in task.model_dump()
    assert not (tmp_path / "tasks.sqlite3").exists()


def test_load_fixture_tasks_is_sorted_deduplicates_release_and_rejects_empty(
    tmp_path: Path,
):
    web = importlib.import_module("surfgym_task.web")

    with pytest.raises(FileNotFoundError, match="no fixture task json files"):
        web.load_fixture_tasks(tmp_path)

    release_hook = {
        "timing": web.DOCKER_FIXTURE_RELEASE_HOOK.timing,
        "script": web.DOCKER_FIXTURE_RELEASE_HOOK.script,
    }
    _write_task(
        tmp_path / "b.json",
        _fixture_task_payload(
            task_id="b",
            hash="b",
            lifecycle_hooks={"release": [release_hook]},
        ),
    )
    _write_task(
        tmp_path / "a.json",
        _fixture_task_payload(task_id="a", hash="a"),
    )

    tasks = web.load_fixture_tasks(tmp_path)

    assert [task.task_id for task in tasks] == ["a", "b"]
    assert all(
        task.lifecycle_hooks.release.count(web.DOCKER_FIXTURE_RELEASE_HOOK) == 1
        for task in tasks
    )


def test_seed_generation_uses_domain_specific_release_hooks() -> None:
    assert _release_hooks("web") == [WEB_STATE_RESET_HOOK]
    assert _release_hooks("gimp") == [DOCKER_FIXTURE_RELEASE_HOOK]
    assert _release_hooks("vlc") == [DOCKER_FIXTURE_RELEASE_HOOK]
    assert "window.surfgym.get" in DOCKER_FIXTURE_RELEASE_HOOK.script
    assert "for (let attempt = 0; attempt < 120; attempt += 1)" in DOCKER_FIXTURE_RELEASE_HOOK.script
