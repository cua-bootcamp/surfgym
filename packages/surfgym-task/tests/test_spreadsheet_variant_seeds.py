import unittest
from pathlib import Path

from surfgym_task.io import SeedReader
from surfgym_task.seed import CriteriaSeedTask

SEEDS_DIR = (
    Path(__file__).parents[1]
    / "src"
    / "surfgym_task"
    / "data"
    / "spreadsheet"
    / "seeds"
)

EXPECTED_SEEDS = {
    "assign_branch_officers",
    "assign_student_grades",
    "count_invoice_occurrences_pivot",
    "summarize_promotion_revenue_columns",
    "embed_two_decimal_value_in_text",
    "format_millions_and_billions",
    "transpose_training_matrix",
    "build_year_profit_labels",
    "calculate_revenue_and_pivot",
    "chart_monthly_totals_and_growth",
    "chart_weekly_sales_and_cogs",
    "chart_two_year_cost_totals",
    "request_csv_export",
    "format_decimal_values_two_places",
    "request_fit_to_one_page_pdf",
}


class OSWorldSpreadsheetVariantSeedTests(unittest.TestCase):
    def test_expected_variant_seeds_exist_and_parse(self):
        missing = sorted(
            seed_name
            for seed_name in EXPECTED_SEEDS
            if not (SEEDS_DIR / f"{seed_name}.json").is_file()
        )
        self.assertEqual(missing, [])

        parsed = {
            seed_name: seed
            for seed, seed_name in SeedReader(SEEDS_DIR).get_seed()
            if seed_name in EXPECTED_SEEDS
        }
        self.assertEqual(set(parsed), EXPECTED_SEEDS)

        for seed_name, seed in parsed.items():
            with self.subTest(seed_name=seed_name):
                self.assertIsInstance(seed, CriteriaSeedTask)
                self.assertEqual(seed.domain, "spreadsheet")
                self.assertEqual(seed.website, "http://localhost:3000/spreadsheet")
                self.assertEqual(len(seed.states), 2)
                self.assertGreater(len(seed.states[0].atoms), 0)
                self.assertGreater(len(seed.states[1].atoms), 0)

    def test_promotion_column_pivot_accounts_for_total_row_header(self):
        seed = next(
            seed
            for seed, seed_name in SeedReader(SEEDS_DIR).get_seed()
            if seed_name == "summarize_promotion_revenue_columns"
        )
        observed = {
            (atom.spec["cell"], atom.spec["property"]): atom.value
            for atom in seed.states[1].atoms
            if atom.spec["kind"] == "cell"
        }

        self.assertEqual(
            observed,
            {
                ("A2", "value"): "Total",
                ("B2", "value"): 2400,
                ("C2", "value"): 1900,
                ("D2", "value"): 2200,
            },
        )

    def test_monthly_growth_values_match_live_formula_engine(self):
        seed = next(
            seed
            for seed, seed_name in SeedReader(SEEDS_DIR).get_seed()
            if seed_name == "chart_monthly_totals_and_growth"
        )
        observed = {
            atom.spec["cell"]: atom.value
            for atom in seed.states[1].atoms
            if atom.spec["kind"] == "cell"
            and atom.spec["property"] == "value"
            and atom.spec["cell"] in {"C6", "D6", "E6", "F6", "G6"}
        }

        self.assertEqual(
            observed,
            {
                "C6": 0.1666666666666667,
                "D6": 0.2857142857142858,
                "E6": 0.1481481481481481,
                "F6": 0.1935483870967742,
                "G6": 0.1891891891891893,
            },
        )

    def test_locale_and_one_page_pdf_variants_use_their_canonical_boundaries(self):
        parsed = {
            seed_name: seed
            for seed, seed_name in SeedReader(SEEDS_DIR).get_seed()
            if seed_name in {
                "format_decimal_values_two_places",
                "request_fit_to_one_page_pdf",
            }
        }
        decimal_seed = parsed["format_decimal_values_two_places"]
        pdf_seed = parsed["request_fit_to_one_page_pdf"]

        self.assertEqual(
            [(atom.spec, atom.value) for atom in decimal_seed.states[1].atoms],
            [
                ({"kind": "cell", "sheet": "Sheet1", "cell": "A1:C1", "property": "numberFormat"}, "0.00"),
                ({"kind": "cell", "sheet": "Sheet1", "cell": "A1", "property": "value"}, 12.34),
                ({"kind": "cell", "sheet": "Sheet1", "cell": "B1", "property": "value"}, -0.75),
                ({"kind": "cell", "sheet": "Sheet1", "cell": "C1", "property": "value"}, 1000.5),
            ],
        )
        self.assertEqual(
            [(atom.spec, atom.value) for atom in pdf_seed.states[1].atoms],
            [
                (
                    {"kind": "export", "property": "request"},
                    {"format": "pdf", "filename": "Project_Budget.pdf", "fitToOnePage": True},
                ),
            ],
        )
        initial_values = [
            atom.value
            for atom in decimal_seed.states[0].atoms
            if atom.spec.get("kind") == "cell" and atom.spec.get("property") == "value"
        ]
        self.assertTrue(all(isinstance(value, (int, float)) for value in initial_values))


if __name__ == "__main__":
    unittest.main()
