import json
import shutil
import sqlite3
from pathlib import Path
from typing import Never

import pytest
from pydantic import TypeAdapter
from surfgym_contracts.task import Task
from surfgym_task.main import augment
from surfgym_task.seed import (
    RawCriteriaSeedTask,
    RawInfeasibleSeedTask,
    RawLLMJudgeSeedTask,
    RawSeedTask,
)

_WORD_COLLABORATION_TASK_ID = "bb8ccc78-479f-4a2f-a71e-d565e439436b"
_WORD_COLLABORATION_INSTRUCTION = (
    "Share this document with my team and let us edit it together in real-time."
)
_SPARKLINE_SEED_NAME = "add_warehouse_throughput_sparklines"


def test_raw_infeasible_seed_parses_without_states():
    raw_seed = TypeAdapter[RawSeedTask](RawSeedTask).validate_python(
        {
            "instruction": "Report that sparklines are unavailable.",
            "website": "http://example.test/spreadsheet",
            "evaluation": {"mode": "infeasible"},
        }
    )

    assert isinstance(raw_seed, RawInfeasibleSeedTask)
    assert raw_seed.evaluation.mode == "infeasible"


def test_raw_infeasible_seed_parses_one_initial_state():
    raw_seed = TypeAdapter[RawSeedTask](RawSeedTask).validate_python(
        {
            "instruction": "Report that sparklines are unavailable.",
            "website": "http://example.test/spreadsheet",
            "states": [
                [
                    {
                        "spec": {
                            "kind": "cell",
                            "sheet": "Sheet1",
                            "cell": "B1",
                            "property": "value",
                        },
                        "value": "Warehouse",
                    }
                ]
            ],
            "evaluation": {"mode": "infeasible"},
        }
    )

    assert isinstance(raw_seed, RawInfeasibleSeedTask)
    assert raw_seed.states is not None
    assert raw_seed.states[0].atoms[0].value == "Warehouse"


def test_infeasible_seed_augment_preserves_id_instruction_and_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    seed_dir = tmp_path / "spreadsheet"
    seed_path = seed_dir / "seeds" / "original-osworld-id.json"
    seed_path.parent.mkdir(parents=True)
    seed_path.write_text(
        json.dumps(
            {
                "instruction": "Create sparklines for every order ID.",
                "website": {
                    "base": "http://example.test/spreadsheet?existing=value",
                    "param": {"surfgym_disabled": "sparkline"},
                },
                "evaluation": {"mode": "infeasible"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fail_generate(*args: object, **kwargs: object) -> Never:
        raise AssertionError("Infeasible seeds must not generate instructions.")

    monkeypatch.setattr(
        "surfgym_task.instruction_generator.InstructionGenerator.generate",
        fail_generate,
    )

    augment(seed_dir=seed_dir, granularity="FINE", profile="SNAPSHOT")

    detail_paths = list((seed_dir / "out" / "detail").glob("*.json"))
    assert len(detail_paths) == 1
    task = Task.model_validate_json(detail_paths[0].read_text(encoding="utf-8"))
    assert task.task_id == "original-osworld-id"
    assert task.instruction == "Create sparklines for every order ID."
    assert task.evaluation.mode == "infeasible"
    assert task.website[0].url == (
        "http://example.test/spreadsheet?existing=value&surfgym_disabled=sparkline"
    )

    with sqlite3.connect(seed_dir / "out" / "tasks.sqlite3") as connection:
        rows = connection.execute("SELECT task_id FROM tasks").fetchall()
    assert rows == [("original-osworld-id",)]


def test_infeasible_seed_augment_uses_initial_state_for_allocate_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    seed_dir = tmp_path / "spreadsheet"
    seed_path = seed_dir / "seeds" / "sparkline-unavailable.json"
    seed_path.parent.mkdir(parents=True)
    seed_path.write_text(
        json.dumps(
            {
                "instruction": "Create sparklines for every warehouse.",
                "website": "http://example.test/spreadsheet",
                "states": [
                    [
                        {
                            "spec": {
                                "kind": "cell",
                                "sheet": "Sheet1",
                                "cell": "B1",
                                "property": "value",
                            },
                            "value": "Warehouse",
                        }
                    ]
                ],
                "evaluation": {"mode": "infeasible"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    augment(seed_dir=seed_dir, granularity="FINE", profile="ROLLOUT")

    detail_path = seed_dir / "out" / "detail" / "sparkline-unavailable.json"
    task = Task.model_validate_json(detail_path.read_text(encoding="utf-8"))
    assert task.evaluation.mode == "infeasible"
    assert len(task.lifecycle_hooks.allocate) == 1
    assert task.lifecycle_hooks.allocate[0].timing == "after"
    assert task.lifecycle_hooks.allocate[0].script == (
        'window.surfgym.set({"kind": "cell", "sheet": "Sheet1", '
        '"cell": "B1", "property": "value"}, "Warehouse")'
    )


def test_existing_criteria_and_llm_seed_variants_still_parse():
    criteria_seed = TypeAdapter[RawSeedTask](RawSeedTask).validate_python(
        {
            "instruction": "Set the status.",
            "website": "http://example.test/spreadsheet",
            "states": [{"atoms": [{"spec": {"id": "status"}, "value": "done"}]}],
        }
    )
    llm_seed = TypeAdapter[RawSeedTask](RawSeedTask).validate_python(
        {
            "instruction": "Complete the task.",
            "website": "http://example.test/spreadsheet",
            "evaluation": {"mode": "llm"},
        }
    )

    assert isinstance(criteria_seed, RawCriteriaSeedTask)
    assert isinstance(llm_seed, RawLLMJudgeSeedTask)
    assert criteria_seed.states[0].atoms[0].value == "done"
    assert llm_seed.evaluation.mode == "llm"


def test_osworld_word_collaboration_seed_generates_one_infeasible_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_seed = (
        Path(__file__).parents[1]
        / "src"
        / "surfgym_task"
        / "data"
        / "word"
        / "seeds"
        / f"{_WORD_COLLABORATION_TASK_ID}.json"
    )
    seed_dir = tmp_path / "word"
    (seed_dir / "seeds").mkdir(parents=True)
    shutil.copy2(source_seed, seed_dir / "seeds" / source_seed.name)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fail_generate(*args: object, **kwargs: object) -> Never:
        raise AssertionError("Infeasible seeds must not generate instructions.")

    monkeypatch.setattr(
        "surfgym_task.instruction_generator.InstructionGenerator.generate",
        fail_generate,
    )

    augment(seed_dir=seed_dir, granularity="COARSE", profile="ROLLOUT")

    detail_paths = list((seed_dir / "out" / "detail").glob("*.json"))
    assert len(detail_paths) == 1
    task = Task.model_validate_json(detail_paths[0].read_text(encoding="utf-8"))
    assert task.task_id == _WORD_COLLABORATION_TASK_ID
    assert task.instruction == _WORD_COLLABORATION_INSTRUCTION
    assert task.evaluation.mode == "infeasible"
    assert task.website[0].url == "http://localhost:3000/word"

    with sqlite3.connect(seed_dir / "out" / "tasks.sqlite3") as connection:
        rows = connection.execute("SELECT task_id FROM tasks").fetchall()
    assert rows == [(_WORD_COLLABORATION_TASK_ID,)]


def test_sparkline_seed_generates_one_infeasible_task_with_initial_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_seed = (
        Path(__file__).parents[1]
        / "src"
        / "surfgym_task"
        / "data"
        / "spreadsheet"
        / "seeds"
        / f"{_SPARKLINE_SEED_NAME}.json"
    )
    seed_dir = tmp_path / "spreadsheet"
    (seed_dir / "seeds").mkdir(parents=True)
    shutil.copy2(source_seed, seed_dir / "seeds" / source_seed.name)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    augment(seed_dir=seed_dir, granularity="COARSE", profile="ROLLOUT")

    detail_paths = list((seed_dir / "out" / "detail").glob("*.json"))
    assert len(detail_paths) == 1
    task = Task.model_validate_json(detail_paths[0].read_text(encoding="utf-8"))
    assert task.task_id == _SPARKLINE_SEED_NAME
    assert task.evaluation.mode == "infeasible"
    assert len(task.lifecycle_hooks.allocate) == 38
    assert all(
        '"kind": "sparkline"' not in hook.script
        for hook in task.lifecycle_hooks.allocate
    )
    assert task.lifecycle_hooks.observe == []

    with sqlite3.connect(seed_dir / "out" / "tasks.sqlite3") as connection:
        rows = connection.execute("SELECT task_id FROM tasks").fetchall()
    assert rows == [(_SPARKLINE_SEED_NAME,)]
