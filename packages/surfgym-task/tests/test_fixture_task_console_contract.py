from pathlib import Path

from surfgym_task.io import SeedReader
from surfgym_task.seed import CriteriaSeedTask


def test_canonical_desktop_seed_corpora_keep_expected_state_atom_counts() -> None:
    data_root = (
        Path(__file__).parents[1]
        / "src"
        / "surfgym_task"
        / "data"
    )
    expected_atom_counts = {"gimp": 32, "vlc": 47, "vscode": 20}

    for app, expected_atom_count in expected_atom_counts.items():
        seeds = SeedReader(data_root / app / "seeds").get_seed()
        atom_count = sum(
            len(state.atoms)
            for seed, _name in seeds
            if isinstance(seed, CriteriaSeedTask)
            for state in seed.states
        )

        assert atom_count == expected_atom_count
        assert not (data_root / app / "tasks").exists()
