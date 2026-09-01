import shutil
import sqlite3
from pathlib import Path
from typing import Never

import pytest
from surfgym_contracts.task import Task
from surfgym_task.main import augment


def test_canonical_seed_without_partial_instruction_skips_instruction_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_seed = (
        Path(__file__).parents[1]
        / "src"
        / "surfgym_task"
        / "data"
        / "spreadsheet"
        / "seeds"
        / "calculate_hired_year.json"
    )
    seed_dir = tmp_path / "spreadsheet"
    (seed_dir / "seeds").mkdir(parents=True)
    shutil.copy2(source_seed, seed_dir / "seeds" / source_seed.name)

    def fail_instruction_client_init(*_args: object, **_kwargs: object) -> Never:
        raise AssertionError("A full canonical seed must not construct InstructionGenerator.")

    monkeypatch.setattr(
        "surfgym_task.io.InstructionGenerator.__init__",
        fail_instruction_client_init,
    )

    augment(seed_dir=seed_dir, granularity="COARSE", profile="ROLLOUT")

    detail_path = (
        seed_dir / "out" / "detail" / "calculate_hired_year" / "0_1.json"
    )
    task = Task.model_validate_json(detail_path.read_text(encoding="utf-8"))
    assert task.instruction == (
        'Calculate each employee\'s completed "Years of Service" based on their hire date. '
        "Do not touch irrelevant regions including blank cells."
    )

    with sqlite3.connect(seed_dir / "out" / "tasks.sqlite3") as connection:
        rows = connection.execute("SELECT task_id FROM tasks").fetchall()
    assert rows == [("calculate_hired_year_0_1",)]
