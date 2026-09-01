from pathlib import Path

from surfgym_task.io import SeedReader
from surfgym_task.seed import CriteriaSeedTask, InfeasibleSeedTask


def _website_base(seed: CriteriaSeedTask | InfeasibleSeedTask) -> str:
    return seed.website if isinstance(seed.website, str) else seed.website.base


def test_web_seed_corpus_registers_without_building_a_database():
    data_dir = Path(__file__).parents[1] / "src" / "surfgym_task" / "data" / "web"

    seeds = list(SeedReader(data_dir / "seeds").get_seed())

    assert len(seeds) == 81
    assert len({name for _, name in seeds}) == 81
    assert all(seed.domain == "web" for seed, _ in seeds)
    assert all(
        _website_base(seed).startswith(("http://localhost:3200/", "http://127.0.0.1:"))
        for seed, _ in seeds
    )
    assert sum(isinstance(seed, CriteriaSeedTask) for seed, _ in seeds) == 79
    assert sum(isinstance(seed, InfeasibleSeedTask) for seed, _ in seeds) == 2
    assert sum(bool(seed.states and seed.states[0].atoms) for seed, _ in seeds) == 46
    setup_criteria = [
        seed for seed, _ in seeds if isinstance(seed, CriteriaSeedTask) and seed.states[0].atoms
    ]
    assert len(setup_criteria) == 46
    assert all(seed.accumulation == "DELTA" for seed in setup_criteria)
    pilot = dict((name, seed) for seed, name in seeds)[
        "prepare_instacart_health_items_order"
    ]
    assert isinstance(pilot, CriteriaSeedTask)
    assert pilot.website == (
        "http://127.0.0.1:8151/store/store_1"
        "?sid=3355ed6f-3f01-5bf3-99ee-a2f1aaff9717"
    )
    assert {atom.spec.get("target") for atom in pilot.states[0].atoms} == {
        "app_state"
    }
    assert len(pilot.states) == 2
    assert not (data_dir / "out" / "tasks.sqlite3").exists()
