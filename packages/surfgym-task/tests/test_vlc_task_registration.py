from pathlib import Path

from surfgym_task.io import SeedReader
from surfgym_task.seed import CriteriaSeedTask, InfeasibleSeedTask, LLMJudgeSeedTask


def _website_base(seed: CriteriaSeedTask | LLMJudgeSeedTask) -> str:
    return seed.website if isinstance(seed.website, str) else seed.website.base


def test_vlc_canonical_seed_corpus_has_expected_evaluation_split() -> None:
    seeds_dir = (
        Path(__file__).parents[1]
        / "src"
        / "surfgym_task"
        / "data"
        / "vlc"
        / "seeds"
    )

    seeds = [seed for seed, _name in SeedReader(seeds_dir).get_seed()]

    assert len(seeds) == 51
    assert sum(isinstance(seed, CriteriaSeedTask) for seed in seeds) == 40
    assert sum(isinstance(seed, LLMJudgeSeedTask) for seed in seeds) == 9
    assert sum(isinstance(seed, InfeasibleSeedTask) for seed in seeds) == 2
    assert sum(
        len(state.atoms)
        for seed in seeds
        if isinstance(seed, CriteriaSeedTask)
        for state in seed.states
    ) == 47
    assert all(seed.domain == "vlc" for seed in seeds)
    assert all(
        _website_base(seed).startswith("http://localhost:53001/vlc")
        for seed in seeds
    )
    assert not (seeds_dir.parent / "tasks").exists()
    assert not (seeds_dir.parent / "out" / "tasks.sqlite3").exists()
