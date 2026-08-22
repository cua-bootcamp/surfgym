import json
from pathlib import Path

from pydantic import TypeAdapter
from surfgym_task.io import SeedReader
from surfgym_task.seed import (
    CriteriaSeedTask,
    Domain,
    InfeasibleSeedTask,
    LLMJudgeSeedTask,
)


def _write_seed(seeds_dir: Path, name: str, payload: dict[str, object]) -> None:
    seeds_dir.mkdir(parents=True, exist_ok=True)
    (seeds_dir / f"{name}.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_vscode_is_a_supported_seed_domain() -> None:
    assert TypeAdapter[Domain](Domain).validate_python("vscode") == "vscode"


def test_vscode_seed_reader_parses_all_evaluation_types(tmp_path: Path) -> None:
    seeds_dir = tmp_path / "vscode" / "seeds"
    website = "http://localhost:53001/vscode"

    _write_seed(
        seeds_dir,
        "criteria",
        {
            "instruction": "Open the project folder.",
            "website": website,
            "states": [
                [
                    {
                        "spec": {"kind": "workspace", "property": "folders"},
                        "value": ["/home/user/project"],
                    }
                ]
            ],
        },
    )
    _write_seed(
        seeds_dir,
        "llm",
        {
            "instruction": "Install the requested extension.",
            "website": website,
            "evaluation": {"mode": "llm"},
        },
    )
    _write_seed(
        seeds_dir,
        "infeasible",
        {
            "instruction": "Perform an unsupported action.",
            "website": website,
            "evaluation": {"mode": "infeasible"},
        },
    )

    seeds = dict((name, seed) for seed, name in SeedReader(seeds_dir).get_seed())

    assert len(seeds) == 3
    assert sum(isinstance(seed, CriteriaSeedTask) for seed in seeds.values()) == 1
    assert sum(isinstance(seed, LLMJudgeSeedTask) for seed in seeds.values()) == 1
    assert sum(isinstance(seed, InfeasibleSeedTask) for seed in seeds.values()) == 1
    assert all(seed.domain == "vscode" for seed in seeds.values())

    criteria = seeds["criteria"]
    assert isinstance(criteria, CriteriaSeedTask)
    assert len(criteria.states) == 2
    assert criteria.states[0].atoms == []
    assert criteria.states[1].atoms[0].value == ["/home/user/project"]


def test_vscode_criteria_seed_can_override_empty_start(tmp_path: Path) -> None:
    seeds_dir = tmp_path / "vscode" / "seeds"
    _write_seed(
        seeds_dir,
        "criteria",
        {
            "instruction": "Open the project folder.",
            "website": "http://localhost:53001/vscode",
            "empty_start": False,
            "states": [
                [
                    {
                        "spec": {"kind": "workspace", "property": "folders"},
                        "value": ["/home/user/project"],
                    }
                ]
            ],
        },
    )

    [(seed, name)] = list(SeedReader(seeds_dir).get_seed())

    assert name == "criteria"
    assert isinstance(seed, CriteriaSeedTask)
    assert len(seed.states) == 1
    assert seed.states[0].atoms[0].value == ["/home/user/project"]
