import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

SCRIPT_ROOT = Path(__file__).parents[1] / "scripts"
REPO_ROOT = Path(__file__).parents[3]
DATA_ROOT = (
    REPO_ROOT
    / "packages"
    / "surfgym-task"
    / "src"
    / "surfgym_task"
    / "data"
)
DECISION_PATH = (
    REPO_ROOT
    / "docs"
    / "superpowers"
    / "audits"
    / "2026-08-23-task-transformation-decisions.json"
)
OSWORLD_ROOT = REPO_ROOT.parent / "OSWorld" / "evaluation_examples" / "examples"

APPROVED_REPLACEMENTS = {
    ("word", "start_live_coauthoring_for_incident_brief"): (
        "bb8ccc78-479f-4a2f-a71e-d565e439436b",
        "packages/surfgym-task/src/surfgym_task/data/word/seeds/"
        "bb8ccc78-479f-4a2f-a71e-d565e439436b.json",
        "The standalone Word fixture cannot provide simultaneous real-time team "
        "editing with invite, presence, synchronization, and multi-user changes.",
    ),
    ("gimp", "convert_exhibit_photo_to_true_cmyk"): (
        "045bf3ff-9077-4b86-b483-a1040a949cff",
        "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/"
        "osworld_045bf3ff_convert_image_cmyk.json",
        "GIMP cannot convert the opened raster document to a true CMYK document "
        "model through the available built-in fixture capability.",
    ),
    ("gimp", "batch_brighten_destination_photos"): (
        "2e6f678f-472d-4c55-99cc-8e7c5c402a71",
        "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/"
        "osworld_2e6f678f_batch_brightness.json",
        "GIMP cannot apply the requested brightness and three named exports through "
        "one built-in multi-file batch workflow.",
    ),
    ("gimp", "trim_museum_walkthrough_clip"): (
        "38f48d40-764e-4e77-a7cf-51dfce880291",
        "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/"
        "osworld_38f48d40_trim_video.json",
        "GIMP cannot trim `fullvideo.mp4` to 00:01-00:03 and export that MP4 segment.",
    ),
    ("gimp", "translate_imagined_audio_from_landscape"): (
        "58d3eeeb-e9d0-499f-962e-fd0db2a744d8",
        "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/"
        "osworld_58d3eeeb_translate_hidden_audio.json",
        "GIMP cannot recover nonexistent hidden audio from the raster image, "
        "transcribe/translate it, and place the translation in a text layer.",
    ),
    ("gimp", "fetch_reykjavik_crest_inside_gimp"): (
        "5ca86c6f-f317-49d8-b6a7-b527541caae8",
        "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/"
        "osworld_5ca86c6f_download_hku_logo.json",
        "GIMP cannot browse a municipal website, find its official crest, and "
        "download it through GIMP-only built-in features.",
    ),
    ("gimp", "vectorize_rock_badge_as_svg"): (
        "62f7fd55-0687-4a43-b6e1-3eda16fc6252",
        "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/"
        "osworld_62f7fd55_convert_logo_svg.json",
        "GIMP cannot automatically convert the opened raster badge into editable "
        "vector paths and a true SVG.",
    ),
    ("gimp", "restore_subject_detail_without_size_growth"): (
        "8ea73f6f-9689-42ad-8c60-195bbf06a7ba",
        "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/"
        "osworld_8ea73f6f_upscale_without_size_growth.json",
        "GIMP cannot guarantee genuine missing-detail recovery at four-times-larger "
        "pixel dimensions while keeping output byte size no larger than the input.",
    ),
    ("gimp", "dim_absent_harbor_sunset_photo"): (
        "e19bd559-633b-4b02-940f-d946248f088e",
        "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/"
        "osworld_e19bd559_reduce_photo_brightness.json",
        "The exact named input `Harbor-Sunset.jpg` is absent, so it cannot be "
        "opened, dimmed, or saved; ordinary single-photo brightness remains supported.",
    ),
    ("gimp", "set_gimp_coral_application_theme"): (
        "fbb548ca-c2a6-4601-9204-e39a2efc507b",
        "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/"
        "osworld_fbb548ca_set_blue_theme.json",
        "GIMP cannot set all application chrome to a built-in application-color "
        "theme named `Coral`; icon theme and canvas color are different capabilities.",
    ),
    ("vlc", "play_cinemacloud_drm_rental"): (
        "7882ed6e-bece-4bf0-bada-c32dc1ddae72",
        "packages/surfgym-task/src/surfgym_task/data/vlc/seeds/"
        "osworld_7882ed6e_play_google_drm_content.json",
        "VLC cannot acquire a CinemaCloud account/license path and directly play "
        "the protected rental while DRM remains enabled.",
    ),
    ("vlc", "auto_match_lake_video_to_ambient_light"): (
        "cb130f0d-d36f-4302-9838-b3baf46139b6",
        "packages/surfgym-task/src/surfgym_task/data/vlc/seeds/"
        "osworld_cb130f0d_adapt_to_room_lighting.json",
        "VLC cannot sense ambient light and continuously adapt playing-video "
        "brightness/contrast; fixed manual effects are distinct.",
    ),
    ("web", "switch_travelhub_to_arabic"): (
        "3720f614-37fd-4d04-8a6b-76f54f8c222d",
        "packages/surfgym-task/src/surfgym_task/data/web/seeds/"
        "osworld_3720f614_set_xenothian_language.json",
        "TravelHub's own language selector cannot select/render Arabic because "
        "Arabic is absent from the UI language catalogue.",
    ),
    ("web", "set_hotel_results_page_size_fifty"): (
        "ae78f875-5b98-4907-bbb5-9c737fc68c03",
        "packages/surfgym-task/src/surfgym_task/data/web/seeds/"
        "osworld_ae78f875_set_search_results_50.json",
        "TravelHub hotel search exposes no user-facing or persistent "
        "results-per-page control for 50 cards; response metadata is not that capability.",
    ),
}


def _load_decisions():
    sys.path.insert(0, str(SCRIPT_ROOT))
    from audit_task_transformations import load_decisions

    return load_decisions


def test_discovery_covers_the_114_seed_scope_exactly_once() -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    from audit_task_transformations import discover_active_seeds

    rows = discover_active_seeds(DATA_ROOT)
    keys = {(row.key.domain, row.key.seed_stem) for row in rows}

    assert len(rows) == len(keys) == 114
    assert sum(row.key.domain == "spreadsheet" for row in rows) == 65
    assert sum(row.key.domain == "word" for row in rows) == 32
    assert sum(
        row.key.domain not in {"spreadsheet", "word"}
        and row.evaluation_mode == "infeasible"
        for row in rows
    ) == 17
    assert {
        row.key.domain
        for row in rows
        if row.key.domain not in {"spreadsheet", "word"}
    } == {"gimp", "vlc", "vscode", "web"}


def test_decisions_use_the_closed_status_and_fidelity_vocabularies() -> None:
    decisions = _load_decisions()(DECISION_PATH)

    assert {decision.transformation_status for decision in decisions.values()} <= {
        "transformed_from_osworld",
        "independent_original",
        "untransformed_osworld",
        "needs_review",
    }
    assert {decision.fidelity_class for decision in decisions.values()} <= {
        "faithful",
        "capability_adapted",
        "interaction_only",
        "infeasible",
        "not_applicable",
    }
    assert all(decision.decision_reason.strip() for decision in decisions.values())
    assert all(decision.evidence_locators for decision in decisions.values())


def test_known_independent_original_anchors_are_not_transform_targets() -> None:
    decisions = _load_decisions()(DECISION_PATH)
    expected = {
        ("spreadsheet", "classify_training_results"),
        ("spreadsheet", "assign_score_grades_with_approximate_vlookup"),
        ("word", "structure_meeting_minutes"),
        ("word", "format_review_status_terms"),
        ("vscode", "builtin_editor_photo_background"),
        ("vscode", "builtin_klingon_language"),
        ("vscode", "combine_two_active_workspaces"),
        ("vscode", "create_daily_file_on_startup"),
    }

    assert all(
        decisions_by_tuple(decisions)[key].transformation_status
        == "independent_original"
        for key in expected
    )


def test_git_evidence_finds_known_seed_introductions() -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    from audit_task_transformations import git_evidence

    word = git_evidence(
        REPO_ROOT,
        "packages/surfgym-task/src/surfgym_task/data/word/seeds/"
        "bb8ccc78-479f-4a2f-a71e-d565e439436b.json",
    )
    spreadsheet = git_evidence(
        REPO_ROOT,
        "packages/surfgym-task/src/surfgym_task/data/spreadsheet/seeds/"
        "add_warehouse_throughput_sparklines.json",
    )

    assert word.introducing_commit == "cb97eb1"
    assert spreadsheet.introducing_commit == "1695ba1"
    assert spreadsheet.last_semantic_change_commit in {"7d9409c", "2353e73"}


def test_git_audit_processes_every_active_seed_and_surfaces_missing_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    import audit_task_transformations as audit

    rows = [
        audit.ActiveSeed(
            key=audit.TaskKey("word", "first"),
            active_seed_path="first.json",
            instruction="first",
            evaluation_mode="criteria",
        ),
        audit.ActiveSeed(
            key=audit.TaskKey("word", "missing"),
            active_seed_path="missing.json",
            instruction="missing",
            evaluation_mode="criteria",
        ),
    ]
    calls: list[str] = []
    monkeypatch.setattr(audit, "discover_active_seeds", lambda _: rows)

    def fake_git_evidence(_: Path, relative_path: str) -> audit.GitEvidence:
        calls.append(relative_path)
        if relative_path == "missing.json":
            raise ValueError("no Git history for missing.json")
        return audit.GitEvidence("introduced", "changed")

    monkeypatch.setattr(audit, "git_evidence", fake_git_evidence)

    with pytest.raises(ValueError, match="no Git history for missing.json"):
        audit.collect_git_evidence(REPO_ROOT, DATA_ROOT)
    assert calls == ["first.json", "missing.json"]


def test_git_evidence_for_decision_uses_validated_predecessor_only_for_new_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    import audit_task_transformations as audit

    new_path = (
        "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/"
        "convert_exhibit_photo_to_true_cmyk.json"
    )
    predecessor = (
        "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/"
        "osworld_045bf3ff_convert_image_cmyk.json"
    )
    seed = audit.ActiveSeed(
        key=audit.TaskKey("gimp", "convert_exhibit_photo_to_true_cmyk"),
        active_seed_path=new_path,
        instruction="New instruction.",
        evaluation_mode="infeasible",
    )
    decision = audit.Decision(
        osworld_source_id="045bf3ff-9077-4b86-b483-a1040a949cff",
        capability_invariant="The capability remains infeasible.",
        transformation_status="transformed_from_osworld",
        fidelity_class="infeasible",
        instruction_relation="source -> active",
        scenario_relation="source -> active",
        data_relation="source -> active",
        asset_relation="source -> active",
        setup_relation="source -> active",
        decision_reason="The surface changed while the invariant remained.",
        evidence_locators=("evidence.md",),
        predecessor_active_seed_path=predecessor,
    )
    calls: list[str] = []

    def no_new_history(_repo_root: Path, relative_path: str) -> audit.GitEvidence:
        calls.append(relative_path)
        if relative_path == new_path:
            raise ValueError(f"no Git history for {relative_path}")
        assert relative_path == predecessor
        return audit.GitEvidence("introduced-old", "changed-old")

    monkeypatch.setattr(audit, "git_evidence", no_new_history)
    assert audit.git_evidence_for_decision(REPO_ROOT, seed, decision) == (
        audit.GitEvidence("introduced-old", "WORKTREE")
    )
    assert calls == [new_path, predecessor]

    calls.clear()
    monkeypatch.setattr(
        audit,
        "git_evidence",
        lambda _repo_root, relative_path: (
            calls.append(relative_path)
            or audit.GitEvidence("introduced-new", "changed-new")
        ),
    )
    assert audit.git_evidence_for_decision(REPO_ROOT, seed, decision) == (
        audit.GitEvidence("introduced-new", "changed-new")
    )
    assert calls == [new_path]


@pytest.mark.parametrize(
    ("predecessor", "message"),
    [
        (None, "requires predecessor_active_seed_path"),
        ("D:/outside/old.json", "must be repository-relative"),
        (
            "packages/surfgym-task/src/surfgym_task/data/gimp/reference/old.json",
            "must stay in the active seed directory",
        ),
        (
            "packages/surfgym-task/src/surfgym_task/data/vlc/seeds/old.json",
            "must stay in the active seed directory",
        ),
    ],
)
def test_git_evidence_for_decision_rejects_invalid_predecessor_fallback(
    predecessor: str | None,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    import audit_task_transformations as audit

    seed = audit.ActiveSeed(
        key=audit.TaskKey("gimp", "new_seed"),
        active_seed_path=(
            "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/new_seed.json"
        ),
        instruction="New instruction.",
        evaluation_mode="infeasible",
    )
    decision = audit.Decision(
        osworld_source_id="source-id",
        capability_invariant="Invariant.",
        transformation_status="transformed_from_osworld",
        fidelity_class="infeasible",
        instruction_relation="source -> active",
        scenario_relation="source -> active",
        data_relation="source -> active",
        asset_relation="source -> active",
        setup_relation="source -> active",
        decision_reason="Reason.",
        evidence_locators=("evidence.md",),
        predecessor_active_seed_path=predecessor,
    )
    monkeypatch.setattr(
        audit,
        "git_evidence",
        lambda *_: (_ for _ in ()).throw(ValueError("no Git history for new seed")),
    )

    with pytest.raises(ValueError, match=message):
        audit.git_evidence_for_decision(REPO_ROOT, seed, decision)


def test_inventory_rendering_is_deterministic_and_complete() -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    from audit_task_transformations import (
        build_inventory,
        render_json,
        render_markdown,
    )

    first = build_inventory(REPO_ROOT, DATA_ROOT, DECISION_PATH)
    second = build_inventory(REPO_ROOT, DATA_ROOT, DECISION_PATH)

    assert first == second

    json_text = render_json(first)
    markdown = render_markdown(first)
    assert json_text == render_json(second)
    assert markdown == render_markdown(second)
    assert '"total": 114' in json_text
    assert "| transformed_from_osworld | 83 |" in markdown
    assert "| independent_original | 31 |" in markdown
    assert "| untransformed_osworld | 0 |" in markdown


def test_rendered_inventory_json_round_trips_in_row_order() -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    from audit_task_transformations import (
        build_inventory,
        render_json,
        render_markdown,
    )

    rows = build_inventory(REPO_ROOT, DATA_ROOT, DECISION_PATH)
    payload = json.loads(render_json(rows))
    expected_actions = {
        "transformed_from_osworld": "Keep unchanged.",
        "independent_original": "Keep unchanged.",
        "untransformed_osworld": "Replace with a transformed seed.",
        "needs_review": "Resolve before any seed edit.",
    }

    assert payload["total"] == 114
    assert payload["counts"] == {
        "transformed_from_osworld": 83,
        "independent_original": 31,
        "untransformed_osworld": 0,
        "needs_review": 0,
    }
    assert [
        (item["domain"], item["seed_stem"]) for item in payload["rows"]
    ] == sorted((row.domain, row.seed_stem) for row in rows)
    assert all(item["evidence_locators"] for item in payload["rows"])
    assert all(item["introducing_commit"] for item in payload["rows"])
    assert all(row.lineage_evidence == row.evidence_locators for row in rows)
    assert all(
        row.required_action == expected_actions[row.transformation_status]
        for row in rows
    )
    assert all(
        item["lineage_evidence"] == item["evidence_locators"]
        and item["required_action"] == expected_actions[item["transformation_status"]]
        for item in payload["rows"]
    )
    markdown = render_markdown(rows)
    assert "lineage evidence" in markdown
    assert "required action" in markdown


def test_markdown_domain_tables_have_matching_column_counts() -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    from audit_task_transformations import build_inventory, render_markdown

    rows = build_inventory(REPO_ROOT, DATA_ROOT, DECISION_PATH)
    lines = render_markdown(rows).splitlines()

    def cell_count(line: str) -> int:
        return sum(
            char == "|" and (index == 0 or line[index - 1] != "\\")
            for index, char in enumerate(line)
        ) - 1

    domains = {row.domain for row in rows}
    for domain in domains:
        section_index = lines.index(f"## {domain}")
        header = lines[section_index + 2]
        delimiter = lines[section_index + 3]
        data_rows = []
        for line in lines[section_index + 4 :]:
            if not line or line.startswith("## "):
                break
            data_rows.append(line)

        assert data_rows
        assert cell_count(delimiter) == cell_count(header)
        assert all(cell_count(row) == cell_count(header) for row in data_rows)


@pytest.mark.parametrize(
    ("status", "expected_action"),
    [
        ("transformed_from_osworld", "Keep unchanged."),
        ("independent_original", "Keep unchanged."),
        ("untransformed_osworld", "Replace with a transformed seed."),
        ("needs_review", "Resolve before any seed edit."),
    ],
)
def test_inventory_row_derives_spec_lineage_evidence_and_required_action(
    status: str,
    expected_action: str,
) -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    import audit_task_transformations as audit

    seed = audit.ActiveSeed(
        key=audit.TaskKey("word", "example"),
        active_seed_path="packages/surfgym-task/data/word/seeds/example.json",
        instruction="Example instruction.",
        evaluation_mode="criteria",
    )
    decision = audit.Decision(
        osworld_source_id=None if status == "independent_original" else "source-id",
        capability_invariant="The capability remains unchanged.",
        transformation_status=status,
        fidelity_class="not_applicable",
        instruction_relation="documented relation",
        scenario_relation="documented relation",
        data_relation="documented relation",
        asset_relation="documented relation",
        setup_relation="documented relation",
        decision_reason="The evidence supports this status.",
        evidence_locators=("current.json", "history: abc1234"),
    )
    row = audit.InventoryRow.from_parts(
        seed,
        decision,
        audit.GitEvidence("abc1234", "def5678"),
    )

    assert row.lineage_evidence == decision.evidence_locators
    assert row.required_action == expected_action

    payload = json.loads(audit.render_json([row]))
    assert payload["rows"][0]["lineage_evidence"] == list(
        decision.evidence_locators
    )
    assert payload["rows"][0]["required_action"] == expected_action

    markdown = audit.render_markdown([row])
    assert "lineage evidence" in markdown
    assert "required action" in markdown
    assert "current.json" in markdown
    assert expected_action in markdown


@pytest.mark.parametrize("failure", ["render", "stage_write", "replace"])
def test_report_publication_keeps_existing_pair_when_a_stage_fails(
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    import audit_task_transformations as audit

    json_path = tmp_path / "inventory.json"
    markdown_path = tmp_path / "inventory.md"
    json_path.write_text("old json\n", encoding="utf-8")
    markdown_path.write_text("old markdown\n", encoding="utf-8")
    monkeypatch.setattr(audit, "build_inventory", lambda *_: [])

    if failure == "render":
        monkeypatch.setattr(
            audit,
            "render_markdown",
            lambda _: (_ for _ in ()).throw(OSError("render failed")),
        )
    elif failure == "stage_write":
        original_write_text = Path.write_text

        def fail_markdown_stage(
            path: Path,
            data: str,
            *args: object,
            **kwargs: object,
        ) -> int:
            if path.suffix == ".tmp" and "inventory.md" in path.name:
                raise OSError("staging write failed")
            return original_write_text(path, data, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_markdown_stage)
    else:
        original_replace = Path.replace

        def fail_markdown_replace(path: Path, target: Path) -> Path:
            if path.suffix == ".tmp" and Path(target).name == "inventory.md":
                raise OSError("replace failed")
            return original_replace(path, target)

        monkeypatch.setattr(Path, "replace", fail_markdown_replace)

    with pytest.raises(OSError):
        audit.main(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--data-root",
                str(DATA_ROOT),
                "--decisions",
                str(DECISION_PATH),
                "--json-out",
                str(json_path),
                "--markdown-out",
                str(markdown_path),
            ]
        )

    assert json_path.read_text(encoding="utf-8") == "old json\n"
    assert markdown_path.read_text(encoding="utf-8") == "old markdown\n"


def test_report_cli_resolves_relative_paths_before_building_inventory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    import audit_task_transformations as audit

    calls: list[tuple[Path, Path, Path]] = []

    def fake_build_inventory(
        repo_root: Path,
        data_root: Path,
        decision_path: Path,
    ) -> list[audit.InventoryRow]:
        calls.append((repo_root, data_root, decision_path))
        return []

    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(audit, "build_inventory", fake_build_inventory)

    assert audit.main(
        [
            "--repo-root",
            ".",
            "--data-root",
            "packages/surfgym-task/src/surfgym_task/data",
            "--decisions",
            "docs/superpowers/audits/2026-08-23-task-transformation-decisions.json",
            "--json-out",
            str(tmp_path / "inventory.json"),
            "--markdown-out",
            str(tmp_path / "inventory.md"),
        ]
    ) == 0
    assert calls == [(REPO_ROOT, DATA_ROOT, DECISION_PATH)]


def test_every_active_seed_has_exactly_one_complete_decision() -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    from audit_task_transformations import discover_active_seeds

    active = discover_active_seeds(DATA_ROOT)
    decisions = _load_decisions()(DECISION_PATH)
    active_keys = {row.key for row in active}

    assert set(decisions) == active_keys
    assert all(decision.capability_invariant.strip() for decision in decisions.values())
    assert all(decision.instruction_relation.strip() for decision in decisions.values())
    assert all(decision.scenario_relation.strip() for decision in decisions.values())
    assert all(decision.data_relation.strip() for decision in decisions.values())
    assert all(decision.asset_relation.strip() for decision in decisions.values())
    assert all(decision.setup_relation.strip() for decision in decisions.values())


def test_frozen_classification_counts_match_the_evidence_review() -> None:
    decisions = _load_decisions()(DECISION_PATH)
    raw_counts = Counter(item.transformation_status for item in decisions.values())
    counts = {
        status: raw_counts[status]
        for status in (
            "transformed_from_osworld",
            "independent_original",
            "untransformed_osworld",
            "needs_review",
        )
    }
    domain_counts = Counter(
        (key.domain, item.transformation_status)
        for key, item in decisions.items()
    )

    assert counts == {
        "transformed_from_osworld": 83,
        "independent_original": 31,
        "untransformed_osworld": 0,
        "needs_review": 0,
    }
    assert domain_counts == {
        ("spreadsheet", "transformed_from_osworld"): 47,
        ("spreadsheet", "independent_original"): 18,
        ("word", "independent_original"): 9,
        ("word", "transformed_from_osworld"): 23,
        ("gimp", "transformed_from_osworld"): 9,
        ("vlc", "transformed_from_osworld"): 2,
        ("vscode", "independent_original"): 4,
        ("web", "transformed_from_osworld"): 2,
    }


def test_transformed_decisions_record_row_specific_source_to_current_deltas() -> None:
    decisions = _load_decisions()(DECISION_PATH)
    transformed = [
        (key, decision)
        for key, decision in decisions.items()
        if decision.transformation_status == "transformed_from_osworld"
        and (key.domain, key.seed_stem) not in APPROVED_REPLACEMENTS
    ]
    relation_fields = (
        "instruction_relation",
        "scenario_relation",
        "data_relation",
        "asset_relation",
        "setup_relation",
    )

    assert len(transformed) == 69
    for field in relation_fields:
        values = [getattr(decision, field) for _key, decision in transformed]
        assert all(" -> " in value for value in values), field
        assert len(set(values)) == len(values), field
    assert len({decision.decision_reason for _key, decision in transformed}) == 69

    osworld_domains = {
        "spreadsheet": "libreoffice_calc",
        "word": "libreoffice_writer",
    }
    osworld_root = REPO_ROOT.parent / "OSWorld" / "evaluation_examples" / "examples"
    for key, decision in transformed:
        seed_path = DATA_ROOT / key.domain / "seeds" / f"{key.seed_stem}.json"
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        original_path = (
            osworld_root
            / osworld_domains[key.domain]
            / f"{decision.osworld_source_id}.json"
        )
        original = json.loads(original_path.read_text(encoding="utf-8"))
        source_instruction = " ".join(original["instruction"].split())
        current_instruction = " ".join(seed["instruction"].split())

        assert source_instruction in decision.instruction_relation
        assert current_instruction in decision.instruction_relation

        source_files = {
            Path(file["path"]).name
            for config in original["config"]
            for file in config.get("parameters", {}).get("files", [])
        }
        assert source_files
        assert all(name in decision.scenario_relation for name in source_files)
        assert all(name in decision.asset_relation for name in source_files)
        assert all(name in decision.setup_relation for name in source_files)

        def artifact_names(value: object) -> set[str]:
            if isinstance(value, str):
                return {Path(value).name}
            if isinstance(value, list):
                return set().union(*(artifact_names(item) for item in value))
            if isinstance(value, dict):
                return set().union(
                    *(
                        artifact_names(item)
                        for name, item in value.items()
                        if name in {"path", "dest"}
                    )
                )
            return set()

        evaluator_artifacts = artifact_names(original["evaluator"].get("result", []))
        evaluator_artifacts |= artifact_names(original["evaluator"].get("expected", []))
        assert all(name in decision.asset_relation for name in evaluator_artifacts)
        assert "no external setup file" in decision.asset_relation
        assert "[->]" not in decision.asset_relation
        assert "System.Object" not in decision.asset_relation
        assert "System.Object" not in decision.decision_reason

        config_types = {config["type"] for config in original["config"]}
        assert all(name in decision.setup_relation for name in config_types)
        evaluator_funcs = original["evaluator"]["func"]
        if isinstance(evaluator_funcs, str):
            evaluator_funcs = [evaluator_funcs]
        assert all(name in decision.data_relation for name in evaluator_funcs)

        website = seed["website"]
        if isinstance(website, dict):
            website = website["base"]
        assert website in decision.scenario_relation
        assert website in decision.setup_relation

        states = seed.get("states", [])
        initial_atoms = states[0] if states else []
        accumulation = seed.get("accumulation") or "CUMULATIVE"
        if accumulation == "CUMULATIVE" and len(states) > 2:
            goal_by_target = {
                json.dumps(atom["spec"], sort_keys=True): atom
                for state in states
                for atom in state
            }
            goal_atoms = list(goal_by_target.values())
        else:
            goal_atoms = states[-1] if len(states) > 1 else []
        assert f"initial={len(initial_atoms)}" in decision.asset_relation
        if accumulation == "CUMULATIVE" and len(states) > 2:
            assert f"cumulative_end={len(goal_atoms)}" in decision.asset_relation
        else:
            assert f"goal={len(goal_atoms)}" in decision.asset_relation

        if initial_atoms:
            initial_spec = initial_atoms[0]["spec"]
            initial_marker = initial_spec.get("cell", initial_spec["property"])
            assert initial_marker in decision.scenario_relation
            assert initial_marker in decision.setup_relation
        if goal_atoms:
            goal_spec = goal_atoms[0]["spec"]
            goal_marker = goal_spec.get("cell", goal_spec["property"])
            assert goal_marker in decision.data_relation
        else:
            assert "none" in decision.data_relation.lower()

        fidelity_marker = decision.fidelity_class.replace("_", "-")
        assert fidelity_marker in decision.decision_reason.lower()


def test_cumulative_transformed_decisions_cover_every_required_window() -> None:
    from surfgym_task.hoare import HoareStateGenerator
    from surfgym_task.io import SeedReader
    from surfgym_task.seed import CriteriaSeedTask

    expected_keys = {
        ("spreadsheet", "annual_change_rate"),
        ("spreadsheet", "calculate_column_sum"),
        ("spreadsheet", "calculate_probe_drift_per_check"),
        ("spreadsheet", "chart_chronological_dispatch_volume"),
        ("spreadsheet", "chart_monthly_library_circulation"),
        ("spreadsheet", "complete_climate_chamber_run_summaries"),
        ("spreadsheet", "complete_fleet_inspection_rollups"),
        ("spreadsheet", "copy_column_to_new_sheet"),
        ("spreadsheet", "create_volunteer_coverage_header"),
        ("spreadsheet", "highlight_weekend_clinic_dates"),
        ("spreadsheet", "standardize_meter_ids"),
        ("spreadsheet", "summarize_monthly_support_tickets"),
        ("spreadsheet", "unpack_tag"),
        ("word", "color_words_by_initial_letter"),
        ("word", "double_space_opening_paragraphs"),
    }
    decisions = decisions_by_tuple(_load_decisions()(DECISION_PATH))
    seeds = {
        (domain, stem): seed
        for domain in ("spreadsheet", "word")
        for seed, stem in SeedReader(DATA_ROOT / domain / "seeds").get_seed()
        if (domain, stem) in expected_keys
    }

    assert set(seeds) == expected_keys

    def fingerprint(atoms: list) -> str:
        payload = [atom.model_dump(mode="json") for atom in atoms]
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    for key in sorted(expected_keys):
        seed = seeds[key]
        assert isinstance(seed, CriteriaSeedTask)
        assert seed.accumulation == "CUMULATIVE"
        assert len(seed.states) > 2

        final_hoare_state = list(HoareStateGenerator("COARSE").generate(seed))[-1]
        end_atoms = final_hoare_state.end_state.atoms
        expected_by_target = {
            atom.cannoncial: atom.model_dump(mode="json")
            for state in seed.states
            for atom in state.atoms
        }
        actual_by_target = {
            atom.cannoncial: atom.model_dump(mode="json") for atom in end_atoms
        }
        assert actual_by_target == expected_by_target

        decision = decisions[key]
        end_token = (
            f"end_state windows={len(seed.states)} atoms={len(end_atoms)} "
            f"sha256={fingerprint(end_atoms)}"
        )
        assert end_token in decision.data_relation
        assert f"raw_windows={len(seed.states)}" in decision.asset_relation
        assert f"cumulative_end={len(end_atoms)}" in decision.asset_relation

        for index, state in enumerate(seed.states):
            assert state.atoms
            first_spec = json.dumps(
                state.atoms[0].spec,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
            window_token = (
                f"window[{index}] atoms={len(state.atoms)} "
                f"sha256={fingerprint(state.atoms)} first_spec={first_spec}"
            )
            assert window_token in decision.data_relation
            if index > 0:
                window_payload = json.dumps(
                    [atom.model_dump(mode="json") for atom in state.atoms],
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                assert f"{window_token} payload={window_payload}" in (
                    decision.data_relation
                )


def test_e19_brightness_evidence_preserves_the_inference_boundary() -> None:
    decisions = decisions_by_tuple(_load_decisions()(DECISION_PATH))
    decision = decisions[("gimp", "dim_absent_harbor_sunset_photo")]
    capability_locator = (
        "packages/surfgym-task/src/surfgym_task/data/gimp/seeds/brighten_photo.json"
    )

    assert capability_locator in decision.evidence_locators
    brighten = json.loads((REPO_ROOT / capability_locator).read_text(encoding="utf-8"))
    brighten_website = brighten["website"]
    assert {"source": "Dark.jpg", "target": "desktop"} in brighten_website[
        "setup_files"
    ]
    assert brighten_website["open_file"] == "Dark.jpg"
    assert brighten["evaluation"]["mode"] == "llm"

    active_path = DATA_ROOT / "gimp" / "seeds" / "dim_absent_harbor_sunset_photo.json"
    active = json.loads(active_path.read_text(encoding="utf-8"))
    original_path = (
        REPO_ROOT.parent
        / "OSWorld"
        / "evaluation_examples"
        / "examples"
        / "gimp"
        / "e19bd559-633b-4b02-940f-d946248f088e.json"
    )
    original = json.loads(original_path.read_text(encoding="utf-8"))

    assert active["instruction"] != original["instruction"]
    assert original["config"] == []
    assert original["evaluator"]["func"] == "infeasible"
    assert "setup_files" not in active["website"]
    assert "open_file" not in active["website"]
    assert active["evaluation"]["mode"] == "infeasible"
    assert "Harbor-Sunset.jpg" in active["instruction"]
    assert "Harbor-Sunset.jpg" in decision.capability_invariant
    assert "absent" in decision.capability_invariant
    assert "no setup" in decision.setup_relation.lower()
    assert decision.transformation_status == "transformed_from_osworld"
    assert decision.fidelity_class == "infeasible"
    assert decision.instruction_relation != "exact"


def test_osworld_derived_rows_have_resolvable_source_evidence() -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    from audit_task_transformations import discover_active_seeds, validate_decisions

    active = discover_active_seeds(DATA_ROOT)
    decisions = _load_decisions()(DECISION_PATH)

    validate_decisions(active, decisions, OSWORLD_ROOT)


def test_approved_replacements_record_transformed_surface_and_exact_reference_bundles() -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    from audit_task_transformations import discover_active_seeds

    active = {
        row.key: row for row in discover_active_seeds(DATA_ROOT)
    }
    decisions = _load_decisions()(DECISION_PATH)
    osworld_domains = {
        "word": "libreoffice_writer",
        "gimp": "gimp",
        "vlc": "vlc",
        "web": "chrome",
    }

    assert len(APPROVED_REPLACEMENTS) == 14
    assert not any(
        item.transformation_status == "untransformed_osworld"
        for item in decisions.values()
    )
    for key_tuple, (source_id, predecessor_path, invariant) in (
        APPROVED_REPLACEMENTS.items()
    ):
        key = next(key for key in decisions if (key.domain, key.seed_stem) == key_tuple)
        decision = decisions[key]
        old_stem = Path(predecessor_path).stem
        old_key = next(
            (
                candidate
                for candidate in decisions
                if candidate.domain == key.domain and candidate.seed_stem == old_stem
            ),
            None,
        )
        original_path = OSWORLD_ROOT / osworld_domains[key.domain] / f"{source_id}.json"
        reference_path = (
            DATA_ROOT
            / key.domain
            / "reference"
            / key.seed_stem
            / f"{source_id}.json"
        )
        original_payload = json.loads(original_path.read_text(encoding="utf-8"))

        assert old_key is None
        assert key in active
        assert decision.osworld_source_id == source_id
        assert decision.transformation_status == "transformed_from_osworld"
        assert decision.fidelity_class == "infeasible"
        assert decision.predecessor_active_seed_path == predecessor_path
        assert decision.capability_invariant == invariant
        assert decision.instruction_relation != "exact"
        assert active[key].instruction != original_payload["instruction"]
        assert original_payload["instruction"] in decision.instruction_relation
        assert active[key].instruction in decision.instruction_relation
        assert reference_path.read_bytes() == original_path.read_bytes()
        locator = reference_path.relative_to(REPO_ROOT).as_posix()
        assert locator in decision.evidence_locators
        assert " -> " in decision.instruction_relation
        assert " -> " in decision.scenario_relation
        assert " -> " in decision.data_relation
        assert " -> " in decision.asset_relation
        assert " -> " in decision.setup_relation


def test_validate_decisions_rejects_an_original_json_with_a_mismatched_id(
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(SCRIPT_ROOT))
    import audit_task_transformations as audit

    key = audit.TaskKey("gimp", "copied_original")
    active = [
        audit.ActiveSeed(
            key=key,
            active_seed_path="gimp/seeds/copied_original.json",
            instruction="Keep this instruction exactly.",
            evaluation_mode="infeasible",
        )
    ]
    decision = audit.Decision(
        osworld_source_id="expected-id",
        capability_invariant="The original operation remains the target.",
        transformation_status="untransformed_osworld",
        fidelity_class="infeasible",
        instruction_relation="exact",
        scenario_relation="copied",
        data_relation="copied",
        asset_relation="copied",
        setup_relation="copied",
        decision_reason="The original is retained.",
        evidence_locators=("evidence.md",),
    )
    original_path = tmp_path / "gimp" / "expected-id.json"
    original_path.parent.mkdir()
    original_path.write_text(
        json.dumps(
            {"id": "different-id", "instruction": active[0].instruction},
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="OSWorld ID mismatch"):
        audit.validate_decisions(active, {key: decision}, tmp_path)


def test_load_decisions_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "decisions.json"
    item = {
        "domain": "spreadsheet",
        "seed_stem": "same_key",
        "osworld_source_id": None,
        "capability_invariant": "The worksheet contains one controlled operation.",
        "transformation_status": "independent_original",
        "fidelity_class": "not_applicable",
        "instruction_relation": "independently authored",
        "scenario_relation": "independently authored",
        "data_relation": "independently authored",
        "asset_relation": "self-contained or no external asset",
        "setup_relation": "current SurfGym seed contract",
        "decision_reason": "The task is a newly authored seed.",
        "evidence_locators": ["design.md"],
    }
    path.write_text(json.dumps({"decisions": [item, item]}), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate decision: spreadsheet/same_key"):
        _load_decisions()(path)


def test_load_decisions_rejects_invalid_vocabularies(tmp_path: Path) -> None:
    path = tmp_path / "decisions.json"
    path.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "domain": "spreadsheet",
                        "seed_stem": "invalid_status",
                        "osworld_source_id": None,
                        "capability_invariant": "The worksheet contains one controlled operation.",
                        "transformation_status": "unsupported",
                        "fidelity_class": "not_applicable",
                        "instruction_relation": "independently authored",
                        "scenario_relation": "independently authored",
                        "data_relation": "independently authored",
                        "asset_relation": "self-contained or no external asset",
                        "setup_relation": "current SurfGym seed contract",
                        "decision_reason": "The task is a newly authored seed.",
                        "evidence_locators": ["design.md"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid transformation status: unsupported"):
        _load_decisions()(path)


def decisions_by_tuple(decisions):
    return {(key.domain, key.seed_stem): value for key, value in decisions.items()}
