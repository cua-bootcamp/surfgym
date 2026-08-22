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


def test_formatter_compacts_each_state_and_preserves_json(tmp_path: Path) -> None:
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
    assert lines[states_index + 1].lstrip().startswith('[{"spec":')
    assert lines[states_index + 1].rstrip().endswith("],")
    assert lines[states_index + 2].lstrip().startswith('[{"spec":')
    assert lines[states_index + 2].rstrip().endswith("]")
    assert lines[states_index + 3] == "  ],"

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


def test_existing_seed_corpus_is_formatted() -> None:
    formatter = _load_formatter()

    assert formatter.main(["--check"]) == 0
