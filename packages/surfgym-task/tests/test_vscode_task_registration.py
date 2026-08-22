from pathlib import Path

from surfgym_task.io import SeedReader
from surfgym_task.seed import (
    CriteriaSeedTask,
    InfeasibleSeedTask,
    LLMJudgeSeedTask,
)


def _website_base(
    seed: CriteriaSeedTask | LLMJudgeSeedTask | InfeasibleSeedTask,
) -> str:
    return seed.website if isinstance(seed.website, str) else seed.website.base


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
