import json
from collections import Counter
from pathlib import Path

RUNS_ROOT = Path(__file__).parents[1] / "runs"


def test_complete_nn_sim_run_results_are_registered() -> None:
    run_dirs = sorted(path for path in RUNS_ROOT.iterdir() if path.is_dir())

    assert [path.name for path in run_dirs] == [
        "20260730T182049+0900",
        "20260730T212423+0900",
        "20260731T202838+0900",
        "20260802T182225+0900",
        "20260802T184039+0900",
        "20260802T184604+0900",
        "20260803T154538+0900",
        "20260803T164425+0900",
    ]

    files = [path for run_dir in run_dirs for path in run_dir.rglob("*") if path.is_file()]
    assert len(files) == 409
    assert Counter(path.suffix for path in files) == {
        ".npy": 204,
        ".png": 142,
        ".csv": 45,
        ".json": 8,
        ".md": 8,
        ".txt": 2,
    }

    for run_dir in run_dirs:
        assert (run_dir / "report.md").is_file()
        manifest_path = run_dir / "data" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["run_id"] == run_dir.name
        assert manifest["pipeline_version"] == "0.1.0"

    assert not any(path.name in {"__pycache__", ".pytest_cache"} for path in RUNS_ROOT.rglob("*"))
