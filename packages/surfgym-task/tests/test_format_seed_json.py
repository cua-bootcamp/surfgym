import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load_formatter() -> ModuleType:
    script_path = (
        Path(__file__).parents[1] / "scripts" / "format_seed_json.py"
    )
    spec = importlib.util.spec_from_file_location("format_seed_json", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_formatter_expands_multi_spec_states_and_preserves_json(
    tmp_path: Path,
) -> None:
    formatter = _load_formatter()
    seeds_dir = tmp_path / "vscode" / "seeds"
    seeds_dir.mkdir(parents=True)
    seed_path = seeds_dir / "unicode.json"
    payload = {
        "instruction": "한국어 지시문",
        "website": "http://localhost:53001/vscode",
        "states": [
            [
                {
                    "spec": {"kind": "setting", "key": "editor.wordWrap"},
                    "value": "줄 바꿈",
                }
            ],
            [
                {
                    "spec": {"kind": "setting", "key": "editor.wordWrap"},
                    "value": "완료",
                },
                {"spec": {"kind": "status"}, "value": True},
            ],
        ],
        "empty_start": False,
    }
    seed_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )

    assert formatter.main([str(seed_path), "--check"]) == 1
    assert formatter.main([str(seed_path)]) == 0

    formatted = seed_path.read_text(encoding="utf-8")
    assert json.loads(formatted) == payload
    assert list(json.loads(formatted)) == list(payload)
    assert "한국어 지시문" in formatted
    assert formatted.endswith("\n")

    lines = formatted.splitlines()
    states_index = lines.index('  "states": [')
    assert lines[states_index + 1].startswith('  [{"spec":')
    assert lines[states_index + 1].rstrip().endswith("],")
    assert lines[states_index + 2] == "  ["
    assert lines[states_index + 3].startswith('    {"spec":')
    assert lines[states_index + 3].rstrip().endswith("},")
    assert lines[states_index + 4].startswith('    {"spec":')
    assert lines[states_index + 4].rstrip().endswith("}")
    assert lines[states_index + 5] == "  ]"
    assert lines[states_index + 6] == "],"

    first_pass = formatted
    assert formatter.main([str(seed_path), "--check"]) == 0
    assert formatter.main([str(seed_path)]) == 0
    assert seed_path.read_text(encoding="utf-8") == first_pass


def test_formatter_directory_selection_excludes_task_json(tmp_path: Path) -> None:
    formatter = _load_formatter()
    data_dir = tmp_path / "data"
    seed_path = data_dir / "gimp" / "seeds" / "seed.json"
    task_path = data_dir / "gimp" / "tasks" / "task.json"
    seed_path.parent.mkdir(parents=True)
    task_path.parent.mkdir(parents=True)
    seed_path.write_text('{"instruction":"seed","website":"url","states":[[]]}')
    task_path.write_text('{"task_id":"task"}')

    task_before = task_path.read_text(encoding="utf-8")
    assert formatter.main([str(data_dir)]) == 0

    assert seed_path.read_text(encoding="utf-8").endswith("\n")
    assert task_path.read_text(encoding="utf-8") == task_before


def test_formatter_preserves_exact_hash_pinned_projection_seed(tmp_path: Path) -> None:
    formatter = _load_formatter()
    data_dir = tmp_path / "data"
    seed_path = data_dir / "web" / "seeds" / "lineage_task.json"
    seed_path.parent.mkdir(parents=True)
    original = '{"instruction":"seed","website":"url","states":[[]]}'
    seed_path.write_text(original, encoding="utf-8")
    manifest_path = data_dir / "web" / "provenance" / "projection" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "status": "PUBLISHED",
                "tasks": [
                    {
                        "seed": seed_path.name,
                        "seed_sha256": hashlib.sha256(original.encode()).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert formatter.main([str(data_dir), "--check"]) == 0
    assert formatter.main([str(seed_path)]) == 0
    assert seed_path.read_text(encoding="utf-8") == original


def test_existing_seed_corpus_is_formatted() -> None:
    formatter = _load_formatter()

    assert formatter.main(["--check"]) == 0
