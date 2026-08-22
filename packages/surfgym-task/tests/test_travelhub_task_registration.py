from pathlib import Path

from surfgym_task.io import SeedReader
from surfgym_task.seed import CriteriaSeedTask, InfeasibleSeedTask


def test_web_seed_corpus_registers_without_building_a_database():
    data_dir = Path(__file__).parents[1] / "src" / "surfgym_task" / "data" / "web"

    seeds = list(SeedReader(data_dir / "seeds").get_seed())

    assert len(seeds) == 38
    assert len({name for _, name in seeds}) == 38
    assert all(seed.domain == "web" for seed, _ in seeds)
    assert all(seed.website.startswith("http://localhost:3200/") for seed, _ in seeds)
    assert sum(isinstance(seed, CriteriaSeedTask) for seed, _ in seeds) == 36
    assert sum(isinstance(seed, InfeasibleSeedTask) for seed, _ in seeds) == 2
    assert sum(bool(seed.states and seed.states[0].atoms) for seed, _ in seeds) == 3
    setup_criteria = [
        seed for seed, _ in seeds if isinstance(seed, CriteriaSeedTask) and seed.states[0].atoms
    ]
    assert len(setup_criteria) == 3
    assert all(seed.accumulation == "DELTA" for seed in setup_criteria)
    assert not (data_dir / "out" / "tasks.sqlite3").exists()
