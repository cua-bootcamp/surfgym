import json
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Never

import pytest
from surfgym_contracts.task import Task
from surfgym_task.io import SeedReader
from surfgym_task.main import augment
from surfgym_task.seed import CriteriaSeedTask, InfeasibleSeedTask
from surfgym_task.web import DOCKER_FIXTURE_RELEASE_HOOK

CHROME_DATA = (
    Path(__file__).parents[1] / "src" / "surfgym_task" / "data" / "chrome"
)
TASK_DATA = CHROME_DATA.parent
SEMANTIC_SEED_STEM = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
EXECUTABLE_STEMS = frozenset(
    {
        "bookmark_illustrated_transformer",
        "clear_amazon_site_data",
        "clear_browsing_data_on_exit",
        "create_2048_desktop_shortcut",
        "create_favorites_bookmark_folder",
        "disable_chrome_dark_mode",
        "enable_do_not_track",
        "enable_safe_browsing",
        "install_unpacked_hello_extension",
        "open_etsy_password_entry",
        "remove_funbrain_startup_page",
        "remove_youtube_history",
        "rename_chrome_profile_to_thomas",
        "restore_closed_tripadvisor_tab",
        "save_llm_agents_page_as_pdf",
        "set_bing_as_default_search_engine",
        "set_largest_default_font_size",
    }
)
INFEASIBLE_STEMS = frozenset(
    {
        "enable_vertical_tabs_in_chrome",
        "set_chrome_interface_language_to_toki_pona",
        "set_global_search_results_page_size_to_seventy_five",
    }
)
SUPPORTED_CHROME_FORMATS = frozenset(
    {
        "chrome_active_url",
        "chrome_appearance_mode",
        "chrome_bookmark_bar_folders_match",
        "chrome_bookmark_bar_urls_match",
        "chrome_desktop_shortcut_exists",
        "chrome_font_size_source_predicate",
        "chrome_pdf_matches_reference",
        "chrome_preference",
        "chrome_preference_path_exists",
        "chrome_safe_browsing_enabled",
        "chrome_sqlite_domain_absent",
        "chrome_startup_source_predicate",
        "chrome_tabs_match_urls",
        "chrome_unpacked_extension_exists",
    }
)
SUPPORTED_SETUP_OPERATIONS = frozenset(
    {
        "chrome_close_tabs",
        "chrome_open_tabs",
        "chrome_seed_history",
        "chrome_set_preference",
    }
)
SOURCE_HISTORY_OFFSETS = (
    3600,
    1631,
    900,
    300,
    1200,
    2400,
    1500,
    1800,
    2100,
    2700,
    3200,
    3700,
    4000,
    4300,
    4700,
    5000,
    5300,
    5600,
    5900,
    6300,
    6700,
    7000,
    7300,
    7600,
    7900,
    8200,
    8500,
    8800,
    9100,
    9400,
    9700,
    10000,
    10300,
    10600,
    10900,
    11200,
    11500,
    11800,
    12100,
    12400,
)


def _read_source_seeds():
    return list(SeedReader(CHROME_DATA / "seeds").get_seed())


def test_all_active_seed_filenames_are_semantic() -> None:
    offenders = [
        path.relative_to(TASK_DATA).as_posix()
        for path in TASK_DATA.glob("*/seeds/*.json")
        if not SEMANTIC_SEED_STEM.fullmatch(path.stem)
        or path.stem.startswith("osworld_")
        or re.search(r"(?:^|_)[0-9a-f]{8}(?:_|$)", path.stem)
    ]

    assert offenders == []


def _read_raw_seed(stem: str) -> dict[str, object]:
    path = CHROME_DATA / "seeds" / f"{stem}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _materialized_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> list[Task]:
    data_dir = tmp_path / "chrome"
    shutil.copytree(CHROME_DATA / "seeds", data_dir / "seeds")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fail_generate(*args: object, **kwargs: object) -> Never:
        raise AssertionError("Full COARSE corpus tasks must preserve source instructions.")

    monkeypatch.setattr(
        "surfgym_task.instruction_generator.InstructionGenerator.generate",
        fail_generate,
    )
    augment(data_dir, granularity="COARSE", profile="ROLLOUT")

    with sqlite3.connect(data_dir / "out" / "tasks.sqlite3") as connection:
        rows = connection.execute("SELECT payload FROM tasks ORDER BY task_id").fetchall()
    return [Task.model_validate_json(payload) for (payload,) in rows]


def test_chrome_corpus_uses_expected_semantic_stems() -> None:
    seed_paths = sorted((CHROME_DATA / "seeds").glob("*.json"))

    assert len(seed_paths) == 20
    assert {path.stem for path in seed_paths} == (
        EXECUTABLE_STEMS | INFEASIBLE_STEMS
    )


def test_chrome_corpus_has_seventeen_criteria_and_three_infeasible_seeds() -> None:
    seeds = [seed for seed, _ in _read_source_seeds()]

    assert sum(isinstance(seed, CriteriaSeedTask) for seed in seeds) == 17
    assert sum(isinstance(seed, InfeasibleSeedTask) for seed in seeds) == 3


def test_every_chrome_criterion_uses_the_explicit_supported_format_contract() -> None:
    formats = {
        atom.spec.get("format")
        for seed, _ in _read_source_seeds()
        if isinstance(seed, CriteriaSeedTask)
        for state in seed.states
        for atom in state.atoms
    }

    assert formats == SUPPORTED_CHROME_FORMATS
    assert all(isinstance(format_name, str) for format_name in formats)
    assert all(format_name.startswith("chrome_") for format_name in formats)


def test_source_weak_predicates_are_preserved_exactly() -> None:
    startup_atom = _read_raw_seed("remove_funbrain_startup_page")["states"][0][0]
    font_atom = _read_raw_seed("set_largest_default_font_size")["states"][0][0]

    assert startup_atom == {
        "spec": {"format": "chrome_startup_source_predicate"},
        "value": True,
    }
    assert font_atom == {
        "spec": {
            "format": "chrome_font_size_source_predicate",
            "min_exclusive": 16,
            "max_exclusive": 99999,
        },
        "value": True,
    }


def test_chrome_setup_uses_only_typed_operations_and_fixture_references() -> None:
    for path in sorted((CHROME_DATA / "seeds").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        website = payload["website"]
        if isinstance(website, str):
            continue

        for operation in website.get("setup_operations", []):
            assert operation["kind"] in SUPPORTED_SETUP_OPERATIONS
            assert "command" not in operation
            assert "shell" not in operation
            if operation["kind"] == "chrome_seed_history":
                assert "urls" not in operation
                assert len(operation["entries"]) == 40
                assert all(
                    set(entry)
                    == {"url", "title", "visit_time_from_now_in_seconds"}
                    for entry in operation["entries"]
                )
                assert tuple(
                    entry["visit_time_from_now_in_seconds"]
                    for entry in operation["entries"]
                ) == SOURCE_HISTORY_OFFSETS
        for fixture in website.get("setup_files", []):
            assert set(fixture) == {"source", "target"}


def test_every_materialized_chrome_criteria_task_has_the_docker_release_hook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    criteria_tasks = [
        task
        for task in _materialized_tasks(tmp_path, monkeypatch)
        if task.evaluation.mode == "criteria"
    ]

    assert len(criteria_tasks) == 17
    assert all(
        task.lifecycle_hooks.release == [DOCKER_FIXTURE_RELEASE_HOOK]
        for task in criteria_tasks
    )


def test_coarse_rollout_materializes_exactly_twenty_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert len(_materialized_tasks(tmp_path, monkeypatch)) == 20
