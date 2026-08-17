import json
import unittest
from pathlib import Path
from typing import cast

from surfgym_task.io import SeedReader
from surfgym_task.seed import CriteriaSeedTask

DATA_ROOT = Path(__file__).parents[1] / "src" / "surfgym_task" / "data"
OFFICE_SEEDS = {
    "spreadsheet": (
        "create_percent_of_grand_total_pivot_tables",
        "freeze_first_row_and_two_columns",
        "create_two_pivot_tables_on_sheet2",
        "add_pass_fail_held_validation",
    ),
    "word": (
        "format_essay_spacing_and_size",
        "set_default_font_times_new_roman",
    ),
}


def read_seed(domain: str, seed_name: str) -> CriteriaSeedTask:
    for seed, current_name in SeedReader(DATA_ROOT / domain / "seeds").get_seed():
        if current_name == seed_name:
            if not isinstance(seed, CriteriaSeedTask):
                raise TypeError(f"Expected criteria seed: {seed_name}")
            return seed
    raise KeyError(seed_name)


def atom_pairs(seed: CriteriaSeedTask) -> list[tuple[dict[str, object], object]]:
    return cast(
        list[tuple[dict[str, object], object]],
        [(atom.spec, atom.value) for atom in seed.states[-1].atoms],
    )


class ExistingTaskAssetTests(unittest.TestCase):
    def test_office_assets_use_meaningful_names_without_provenance(self):
        for domain, seed_names in OFFICE_SEEDS.items():
            for seed_name in seed_names:
                with self.subTest(domain=domain, seed_name=seed_name):
                    seed_path = DATA_ROOT / domain / "seeds" / f"{seed_name}.json"
                    payload = json.loads(seed_path.read_text(encoding="utf-8"))
                    self.assertNotIn("id", payload)
                    self.assertNotIn("uuid", payload)
                    self.assertNotIn("provenance", payload)
                    self.assertEqual(read_seed(domain, seed_name).domain, domain)

    def test_freeze_panes_task_is_a_runnable_canonical_asset(self):
        seed = read_seed("spreadsheet", "freeze_first_row_and_two_columns")
        self.assertEqual(seed.domain, "spreadsheet")
        self.assertEqual(seed.website, "http://localhost:3000/spreadsheet")
        self.assertEqual(len(seed.states), 2)
        self.assertEqual(
            atom_pairs(seed),
            [
                ({"kind": "sheet", "sheet": "Sheet1", "property": "frozenRows"}, 1),
                ({"kind": "sheet", "sheet": "Sheet1", "property": "frozenColumns"}, 2),
            ],
        )

    def test_three_paragraph_spacing_task_is_a_runnable_canonical_asset(self):
        seed = read_seed("word", "format_essay_spacing_and_size")
        self.assertEqual(seed.domain, "word")
        self.assertEqual(seed.website, "http://localhost:3000/word")
        self.assertEqual(len(seed.states), 2)
        self.assertEqual(
            atom_pairs(seed),
            [
                ({"kind": "paragraph", "index": 0, "property": "lineSpacing"}, 1),
                ({"kind": "paragraph", "index": 1, "property": "lineSpacing"}, 2),
                ({"kind": "paragraph", "index": 2, "property": "lineSpacing"}, 1.5),
                ({"kind": "document", "property": "fontSizeOnly"}, 12),
            ],
        )
