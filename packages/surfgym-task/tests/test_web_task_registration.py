import importlib
import json
from pathlib import Path

import pytest


def _web_task_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "task_id": "travel-search",
        "hash": "travel-search",
        "instruction": "Search for a flight.",
        "website": {
            "base": "http://localhost:3200/search?locale=en",
            "param": {"origin": "New York", "direct": "true"},
        },
        "complexity": 2,
        "evaluation": {
            "operator": "and",
            "criteria": [{"target": "url", "match": "contains", "value": "origin="}],
        },
    }
    payload.update(overrides)
    return payload


def _write_task(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_web_tasks_normalizes_legacy_location_and_registers_reset(tmp_path: Path):
    web = importlib.import_module("surfgym_task.web")
    _write_task(tmp_path / "travel.json", _web_task_payload())

    tasks = web.load_web_tasks(tmp_path)

    assert len(tasks) == 1
    task = tasks[0]
    assert task.task_id == "travel-search"
    assert task.website[0].url == (
        "http://localhost:3200/search?locale=en&origin=New+York&direct=true"
    )
    assert task.lifecycle_hooks.release == [web.WEB_STATE_RESET_HOOK]


def test_load_web_tasks_preserves_existing_lifecycle_hooks(tmp_path: Path):
    web = importlib.import_module("surfgym_task.web")
    allocate_hook = {
        "timing": "after",
        "script": "fetch('/api/state', { method: 'PATCH' })",
    }
    _write_task(
        tmp_path / "travel.json",
        _web_task_payload(lifecycle_hooks={"allocate": [allocate_hook]}),
    )

    task = web.load_web_tasks(tmp_path)[0]

    assert [
        hook.model_dump(exclude_defaults=True) for hook in task.lifecycle_hooks.allocate
    ] == [allocate_hook]
    assert task.lifecycle_hooks.release == [web.WEB_STATE_RESET_HOOK]


def test_load_web_tasks_rejects_mismatched_legacy_hash(tmp_path: Path):
    web = importlib.import_module("surfgym_task.web")
    _write_task(tmp_path / "travel.json", _web_task_payload(hash="different-task"))

    with pytest.raises(ValueError, match="legacy hash must match task_id"):
        web.load_web_tasks(tmp_path)


def test_load_web_tasks_rejects_unknown_legacy_location_fields(tmp_path: Path):
    web = importlib.import_module("surfgym_task.web")
    _write_task(
        tmp_path / "travel.json",
        _web_task_payload(
            website={
                "base": "http://localhost:3200/search",
                "param": {},
                "unexpected": "value",
            }
        ),
    )

    with pytest.raises(ValueError, match="unsupported website fields"):
        web.load_web_tasks(tmp_path)


def test_load_web_tasks_is_sorted_and_rejects_empty_directories(tmp_path: Path):
    web = importlib.import_module("surfgym_task.web")

    with pytest.raises(FileNotFoundError, match="no web task json files"):
        web.load_web_tasks(tmp_path)

    _write_task(tmp_path / "b.json", _web_task_payload(task_id="b", hash="b"))
    _write_task(tmp_path / "a.json", _web_task_payload(task_id="a", hash="a"))

    assert [task.task_id for task in web.load_web_tasks(tmp_path)] == ["a", "b"]
