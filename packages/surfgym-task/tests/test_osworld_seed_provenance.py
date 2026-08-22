import json
from pathlib import Path

from surfgym_task.io import SeedReader

PACKAGE_ROOT = Path(__file__).parents[1]
DATA_ROOT = PACKAGE_ROOT / "src" / "surfgym_task" / "data"
MANIFEST_PATH = Path(__file__).parent / "data" / "osworld_seed_provenance.json"

EXPECTED_MAPPINGS = [
    {
        "domain": "spreadsheet",
        "osworld_id": "4188d3a4-077d-46b7-9c86-23e1a036f6c1",
        "seed_name": "freeze_first_row_and_two_columns",
        "relation": "capability_match",
    },
    {
        "domain": "spreadsheet",
        "osworld_id": "ecb0df7a-4e8d-4a03-b162-053391d3afaf",
        "seed_name": "add_pass_fail_held_validation",
        "relation": "capability_match",
    },
    {
        "domain": "spreadsheet",
        "osworld_id": "535364ea-05bd-46ea-9937-9f55c68507e8",
        "seed_name": "create_two_pivot_tables_on_sheet2",
        "relation": "capability_adaptation",
    },
    {
        "domain": "spreadsheet",
        "osworld_id": "30e3e107-1cfb-46ee-a755-2cd080d7ba6a",
        "seed_name": "create_percent_of_grand_total_pivot_tables",
        "relation": "capability_adaptation",
    },
    {
        "domain": "word",
        "osworld_id": "b21acd93-60fd-4127-8a43-2f5178f4a830",
        "seed_name": "format_essay_spacing_and_size",
        "relation": "capability_match",
    },
    {
        "domain": "word",
        "osworld_id": "f178a4a9-d090-4b56-bc4c-4b72a61a035d",
        "seed_name": "set_default_font_times_new_roman",
        "relation": "scope_normalized_adaptation",
    },
]


def read_manifest() -> list[dict[str, str]]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_records_the_six_audited_office_mappings_once() -> None:
    mappings = read_manifest()

    assert mappings == EXPECTED_MAPPINGS
    assert len({item["osworld_id"] for item in mappings}) == len(mappings)
    assert len({(item["domain"], item["seed_name"]) for item in mappings}) == len(mappings)


def test_manifest_references_matching_osworld_originals() -> None:
    for mapping in read_manifest():
        reference_path = (
            DATA_ROOT / mapping["domain"] / "reference" / f"{mapping['osworld_id']}.json"
        )
        reference = json.loads(reference_path.read_text(encoding="utf-8"))

        assert reference["id"] == mapping["osworld_id"]


def test_manifest_seeds_exist_parse_and_keep_provenance_external() -> None:
    mappings = read_manifest()
    parsed_by_domain = {
        domain: {
            seed_name: seed
            for seed, seed_name in SeedReader(DATA_ROOT / domain / "seeds").get_seed()
        }
        for domain in {mapping["domain"] for mapping in mappings}
    }

    for mapping in mappings:
        seed_path = DATA_ROOT / mapping["domain"] / "seeds" / f"{mapping['seed_name']}.json"
        payload = json.loads(seed_path.read_text(encoding="utf-8"))

        assert mapping["seed_name"] in parsed_by_domain[mapping["domain"]]
        assert {"id", "uuid", "provenance"}.isdisjoint(payload)
