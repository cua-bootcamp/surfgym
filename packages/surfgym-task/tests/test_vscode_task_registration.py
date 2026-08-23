import shutil
import sqlite3
from pathlib import Path

import pytest
from pydantic import TypeAdapter
from surfgym_contracts.task import Task
from surfgym_task.io import SeedReader
from surfgym_task.main import augment
from surfgym_task.seed import (
    CriteriaSeedTask,
    InfeasibleSeedTask,
    LLMJudgeSeedTask,
)
from surfgym_task.web import DOCKER_FIXTURE_RELEASE_HOOK


def _website_base(
    seed: CriteriaSeedTask | LLMJudgeSeedTask | InfeasibleSeedTask,
) -> str:
    return seed.website


def test_vscode_canonical_seed_corpus_has_approved_evaluation_split() -> None:
    seeds_dir = (
        Path(__file__).parents[1]
        / "src"
        / "surfgym_task"
        / "data"
        / "vscode"
        / "seeds"
    )

    seeds = [seed for seed, _name in SeedReader(seeds_dir).get_seed()]

    assert len(seeds) == 23
    assert sum(isinstance(seed, CriteriaSeedTask) for seed in seeds) == 17
    assert sum(isinstance(seed, LLMJudgeSeedTask) for seed in seeds) == 2
    assert sum(isinstance(seed, InfeasibleSeedTask) for seed in seeds) == 4
    assert all(seed.domain == "vscode" for seed in seeds)
    assert all(
        _website_base(seed).startswith("http://localhost:53001/vscode")
        for seed in seeds
    )
    assert not (seeds_dir.parent / "tasks").exists()


def test_generated_vscode_canonical_tasks_register_one_docker_release_hook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_seed_dir = (
        Path(__file__).parents[1]
        / "src"
        / "surfgym_task"
        / "data"
        / "vscode"
        / "seeds"
    )
    seed_dir = tmp_path / "vscode"
    shutil.copytree(source_seed_dir, seed_dir / "seeds")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def generate_instruction(*_args: object, **_kwargs: object) -> str:
        return "Complete the requested VS Code change."

    monkeypatch.setattr(
        "surfgym_task.io.InstructionGenerator.generate",
        generate_instruction,
    )

    augment(seed_dir, granularity="COARSE", profile="ROLLOUT")

    with sqlite3.connect(seed_dir / "out" / "tasks.sqlite3") as connection:
        tasks = [
            TypeAdapter(Task).validate_json(row[0])
            for row in connection.execute("SELECT payload FROM tasks")
        ]

    seed_names = {path.stem for path in (seed_dir / "seeds").glob("*.json")}

    assert len(seed_names) == 23
    assert all(
        any(
            task.task_id == seed_name or task.task_id.startswith(f"{seed_name}_")
            for task in tasks
        )
        for seed_name in seed_names
    )
    assert all(
        task.lifecycle_hooks.release.count(DOCKER_FIXTURE_RELEASE_HOOK) == 1
        for task in tasks
    )
