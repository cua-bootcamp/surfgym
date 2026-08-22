from pathlib import Path

from surfgym_task.io import SeedReader
from surfgym_task.seed import CriteriaSeedTask, InfeasibleSeedTask, LLMJudgeSeedTask


def _website_base(seed: CriteriaSeedTask | LLMJudgeSeedTask) -> str:
    return seed.website if isinstance(seed.website, str) else seed.website.base


def test_gimp_canonical_seed_corpus_has_expected_evaluation_split() -> None:
    seeds_dir = (
        Path(__file__).parents[1]
        / "src"
        / "surfgym_task"
        / "data"
        / "gimp"
        / "seeds"
    )

    seeds = [seed for seed, _name in SeedReader(seeds_dir).get_seed()]

    assert len(seeds) == 64
    assert sum(isinstance(seed, CriteriaSeedTask) for seed in seeds) == 30
    assert sum(isinstance(seed, LLMJudgeSeedTask) for seed in seeds) == 25
    assert sum(isinstance(seed, InfeasibleSeedTask) for seed in seeds) == 9
    assert sum(
        len(state.atoms)
        for seed in seeds
        if isinstance(seed, CriteriaSeedTask)
        for state in seed.states
    ) == 32
    assert all(seed.domain == "gimp" for seed in seeds)
    assert all(
        _website_base(seed).startswith("http://localhost:53001/gimp")
        for seed in seeds
    )
    assert not (seeds_dir.parent / "tasks").exists()
    assert not (seeds_dir.parent / "out" / "tasks.sqlite3").exists()
