import json
import unittest
from pathlib import Path
from typing import cast

from pydantic import TypeAdapter
from surfgym_task.hoare import HoareStateGenerator
from surfgym_task.seed import LegacyStateAtom, RawSeedTask, SeedTask, SpecStateAtom, StateAtom


class SpecStateAtomTest(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "kind": "cell",
            "sheet": "Sheet1",
            "cell": "A1",
            "property": "value",
            "value": "hello",
        }
        self.atom: StateAtom = cast(StateAtom, TypeAdapter(StateAtom).validate_python(self.payload))

    def test_serializes_fixture_spec_directly(self) -> None:
        self.assertIsInstance(self.atom, SpecStateAtom)
        self.assertEqual(
            self.atom.to_script("eval"),
            '(() => {\n    return window.surfgym.get({"kind": "cell", "sheet": "Sheet1", '
            '"cell": "A1", "property": "value"})\n})()',
        )
        self.assertEqual(
            self.atom.to_script("action"),
            '(() => {\n    return window.surfgym.set({"kind": "cell", "sheet": "Sheet1", '
            '"cell": "A1", "property": "value"}, "hello")\n})()',
        )

    def test_uses_spec_as_state_identity_and_instruction_text(self) -> None:
        self.assertEqual(
            self.atom.identity_payload(),
            {
                "kind": "cell",
                "sheet": "Sheet1",
                "cell": "A1",
                "property": "value",
            },
        )
        self.assertEqual(
            self.atom.to_string(),
            'cell(sheet="Sheet1", cell="A1").value = "hello"',
        )

    def test_cumulative_state_keeps_the_latest_value_for_the_same_spec(self) -> None:
        updated_payload = {**self.payload, "value": "updated"}
        seed = SeedTask.model_validate(
            {
                "website": "http://localhost:3000/spreadsheet",
                "domain": "spreadsheet",
                "instruction": "Update A1.",
                "states": [[self.payload], [updated_payload]],
                "accumulation": "CUMULATIVE",
            }
        )

        [state] = HoareStateGenerator(granularity="COARSE").generate(seed)

        self.assertEqual(len(state.end_state), 1)
        self.assertEqual(state.end_state[0].value, "updated")


class SpreadsheetSeedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.seeds_dir = (
            Path(__file__).parents[1]
            / "src"
            / "surfgym_task"
            / "data"
            / "spreadsheet"
            / "seeds"
        )

    def test_active_spreadsheet_seeds_use_specs(self) -> None:
        paths = list(self.seeds_dir.glob("*.json"))
        self.assertEqual(len(paths), 39)

        for path in paths:
            with self.subTest(path=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                seed = RawSeedTask.model_validate(payload)
                self.assertTrue(
                    all(isinstance(atom, SpecStateAtom) for state in seed.states for atom in state)
                )

    def test_active_spreadsheet_specs_use_supported_shapes(self) -> None:
        supported_properties = {
            "cell": {
                "backgroundColor",
                "bold",
                "fontColor",
                "formula",
                "numberFormat",
                "rowHidden",
                "value",
                "valueType",
            },
            "sheet": {"name"},
            "workbook": {"sheetNames"},
            "chart": {
                "categoryData",
                "chartType",
                "context",
                "dataOrientation",
                "height",
                "legendPosition",
                "position",
                "range",
                "seriesData",
                "sourceRange",
                "title",
                "width",
                "xAxisTitle",
                "yAxisTitle",
            },
        }

        for path in self.seeds_dir.glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for state in payload["states"]:
                for atom in state:
                    with self.subTest(path=path.name, atom=atom):
                        self.assertNotIn("query", atom)
                        self.assertNotIn("path", atom)
                        self.assertIn(atom["property"], supported_properties[atom["kind"]])
                        if atom["kind"] != "workbook":
                            self.assertIn("sheet", atom)
                        if atom["kind"] == "cell":
                            self.assertIsInstance(atom["cell"], str)

    def test_hide_tbd_seed_hides_exactly_the_tbd_rows(self) -> None:
        payload = json.loads(
            (self.seeds_dir / "hide_tbd_row.json").read_text(encoding="utf-8")
        )
        initial, final = payload["states"]
        tbd_cells = {atom["cell"] for atom in initial if atom.get("value") == "TBD"}
        hidden_cells = {
            atom["cell"] for atom in final if atom.get("property") == "rowHidden"
        }

        self.assertEqual(hidden_cells, tbd_cells)

    def test_sheet_backup_seed_has_a_complete_delta_final_state(self) -> None:
        payload = json.loads(
            (self.seeds_dir / "sheet_backup_copy_not_move.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["accumulation"], "DELTA")
        self.assertEqual(len(payload["states"]), 2)

        final = payload["states"][1]
        [workbook] = [atom for atom in final if atom["kind"] == "workbook"]
        self.assertEqual(
            workbook["value"],
            ["LARS Resources", "LARS Resources (Backup)", "LARS Resources (Offline)"],
        )

        expected_original = {
            "A1": "Resource",
            "B1": "Owner",
            "A2": "Drone Kit",
            "B2": "Mina",
            "A3": "Battery Pack",
            "B3": "Jules",
        }
        cells_by_sheet = {
            sheet: {
                atom["cell"]: atom["value"]
                for atom in final
                if atom["kind"] == "cell" and atom["sheet"] == sheet
            }
            for sheet in (
                "LARS Resources",
                "LARS Resources (Backup)",
                "LARS Resources (Offline)",
            )
        }
        self.assertEqual(cells_by_sheet["LARS Resources"], expected_original)
        self.assertEqual(cells_by_sheet["LARS Resources (Backup)"], expected_original)
        self.assertEqual(
            cells_by_sheet["LARS Resources (Offline)"],
            {"A1": "Offline Notes", "A2": "Local copy only"},
        )

    def test_annual_change_instruction_matches_its_evaluated_table(self) -> None:
        payload = json.loads(
            (self.seeds_dir / "annual_change_rate.json").read_text(encoding="utf-8")
        )

        self.assertIn("Cash Reserve", payload["instruction"])
        self.assertIn("F2:I6", payload["instruction"])
        self.assertNotIn("Sheet2", payload["instruction"])


class LegacyStateAtomTest(unittest.TestCase):
    def test_query_path_states_remain_supported_for_other_domains(self) -> None:
        payload = {
            "query": [["text", "hello"]],
            "path": ["bold"],
            "value": True,
        }
        atom = cast(StateAtom, TypeAdapter(StateAtom).validate_python(payload))

        self.assertIsInstance(atom, LegacyStateAtom)
        self.assertEqual(
            atom.identity_payload(),
            {"query": [("text", "hello")], "path": ["bold"]},
        )


if __name__ == "__main__":
    unittest.main()
