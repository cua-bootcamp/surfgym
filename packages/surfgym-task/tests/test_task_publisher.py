from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from surfgym_contracts.task import Task
from surfgym_task.main import _DEFAULT_PUBLISH_DOMAINS, parse_args, publish
from surfgym_task.web import DOCKER_FIXTURE_RELEASE_HOOK

SOURCE_DATA = Path(__file__).parents[1] / "src" / "surfgym_task" / "data"


def _copy_seed(data_root: Path, domain: str, seed_name: str) -> None:
    destination = data_root / domain / "seeds"
    destination.mkdir(parents=True)
    shutil.copy2(SOURCE_DATA / domain / "seeds" / f"{seed_name}.json", destination)


def _copy_domain(data_root: Path, domain: str) -> None:
    source = SOURCE_DATA / domain
    destination = data_root / domain
    shutil.copytree(source / "seeds", destination / "seeds")
    instructions = source / "instructions.sqlite3"
    if instructions.is_file():
        shutil.copy2(instructions, destination / instructions.name)


def test_publish_unions_selected_domains_and_preserves_domain_outputs(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _copy_seed(data_root, "spreadsheet", "calculate_hired_year")
    _copy_seed(data_root, "word", "align_notice_sections")
    output_path = tmp_path / "runtime" / "tasks.sqlite3"

    summary = publish(
        data_root=data_root,
        domains=["spreadsheet", "word"],
        output_path=output_path,
        granularity="COARSE",
        profile="ROLLOUT",
    )

    with sqlite3.connect(output_path) as connection:
        task_ids = [
            row[0] for row in connection.execute("SELECT task_id FROM tasks ORDER BY task_id")
        ]

    assert summary.seed_count == 2
    assert summary.task_count == 2
    assert task_ids == ["align_notice_sections_0_1", "calculate_hired_year_0_1"]
    for domain, task_id in (
        ("spreadsheet", "calculate_hired_year"),
        ("word", "align_notice_sections"),
    ):
        assert (data_root / domain / "instructions.sqlite3").is_file()
        assert (data_root / domain / "out" / "detail" / task_id / "0_1.json").is_file()
        assert not (data_root / domain / "out" / "tasks.sqlite3").exists()


def test_publish_rejects_duplicate_ids_before_mutating_output(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _copy_seed(data_root, "spreadsheet", "calculate_hired_year")
    _copy_seed(data_root, "word", "align_notice_sections")
    for domain, source_name in (
        ("spreadsheet", "calculate_hired_year"),
        ("word", "align_notice_sections"),
    ):
        source = data_root / domain / "seeds" / f"{source_name}.json"
        source.rename(source.with_name("shared.json"))
    output_path = tmp_path / "runtime" / "tasks.sqlite3"
    output_path.parent.mkdir(parents=True)
    output_path.write_bytes(b"unchanged-output")

    with pytest.raises(ValueError, match="Duplicate task id shared_0_1") as error:
        publish(
            data_root=data_root,
            domains=["spreadsheet", "word"],
            output_path=output_path,
            granularity="COARSE",
            profile="ROLLOUT",
        )

    assert "spreadsheet/shared.json" in str(error.value)
    assert "word/shared.json" in str(error.value)
    assert output_path.read_bytes() == b"unchanged-output"
    assert not (data_root / "spreadsheet" / "out").exists()
    assert not (data_root / "word" / "out").exists()


def test_publish_rejects_duplicate_workspace_lineage_before_mutating_output(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    seed_names = (
        "brighten_presentation_image_in_gimp",
        "open_desktop_project_from_terminal",
    )
    seed_dir = data_root / "workspace" / "seeds"
    seed_dir.mkdir(parents=True)
    for seed_name in seed_names:
        path = seed_dir / f"{seed_name}.json"
        shutil.copy2(SOURCE_DATA / "workspace" / "seeds" / path.name, path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["source_task_id"] = "shared-source-id"
        path.write_text(json.dumps(payload), encoding="utf-8")
    output_path = tmp_path / "runtime" / "tasks.sqlite3"
    output_path.parent.mkdir(parents=True)
    output_path.write_bytes(b"unchanged-output")

    with pytest.raises(ValueError, match="Duplicate workspace source_task_id") as error:
        publish(
            data_root=data_root,
            domains=["workspace"],
            output_path=output_path,
            granularity="COARSE",
            profile="ROLLOUT",
        )

    assert "workspace/brighten_presentation_image_in_gimp.json" in str(error.value)
    assert "workspace/open_desktop_project_from_terminal.json" in str(error.value)
    assert output_path.read_bytes() == b"unchanged-output"
    assert not (data_root / "workspace" / "out").exists()


def test_publish_cli_accepts_repeatable_explicit_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "surfgym_task.main",
            "publish",
            "--domain",
            "spreadsheet",
            "--domain",
            "word",
            "--output",
            ".runtime/tasks/tasks.sqlite3",
        ],
    )

    args = parse_args()

    assert args.seed_dir == Path("publish")
    assert args.domain == ["spreadsheet", "word"]
    assert args.output == Path(".runtime/tasks/tasks.sqlite3")


def test_publish_materializes_the_current_all_domain_coarse_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "data"
    domains = [
        "chrome",
        "gimp",
        "impress",
        "spreadsheet",
        "vlc",
        "vscode",
        "web",
        "word",
        "workspace",
    ]
    assert _DEFAULT_PUBLISH_DOMAINS == tuple(domains)
    for domain in domains:
        _copy_domain(data_root, domain)
    output_path = tmp_path / "runtime" / "tasks.sqlite3"
    monkeypatch.setattr("surfgym_task.io.InstructionGenerator.__init__", lambda self: None)
    monkeypatch.setattr(
        "surfgym_task.io.InstructionGenerator.generate",
        lambda self, seed, state: f"Generated instruction for {seed.instruction}",
    )

    summary = publish(
        data_root=data_root,
        domains=domains,
        output_path=output_path,
        granularity="COARSE",
        profile="ROLLOUT",
    )

    with sqlite3.connect(output_path) as connection:
        task_count, unique_count = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT task_id) FROM tasks"
        ).fetchone()
        workspace_rows = connection.execute(
            "SELECT task_id, payload FROM tasks WHERE task_id IN (?, ?) ORDER BY task_id",
            (
                "brighten_presentation_image_in_gimp_0_1",
                "open_desktop_project_from_terminal_0_1",
            ),
        ).fetchall()

    assert summary.seed_count == 403
    assert summary.task_count == 504
    assert (task_count, unique_count) == (504, 504)
    assert [task_id for task_id, _payload in workspace_rows] == [
        "brighten_presentation_image_in_gimp_0_1",
        "open_desktop_project_from_terminal_0_1",
    ]
    for _task_id, payload in workspace_rows:
        task = Task.model_validate(json.loads(payload))
        assert len(task.website) == 1
        assert task.website[0].surface == "native"
        assert urlsplit(task.website[0].url).path == "/workspace"
        assert task.lifecycle_hooks.release == [DOCKER_FIXTURE_RELEASE_HOOK]
        assert "artifacts" not in task.model_dump(mode="json")
