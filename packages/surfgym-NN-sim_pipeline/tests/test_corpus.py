import json

from surfgym_nn_sim_pipeline.corpus import load_surfgym_instructions


def _write_task(path, *, instruction, task_id=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"instruction": instruction}
    if task_id is not None:
        payload["task_id"] = task_id
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_surfgym_instructions_uses_only_canonical_seeds(tmp_path):
    _write_task(
        tmp_path / "gimp" / "seeds" / "add_border.json",
        instruction="Use the GIMP seed.",
    )
    _write_task(
        tmp_path / "vlc" / "seeds" / "loop_video.json",
        instruction="Use the VLC seed.",
        task_id="",
    )
    _write_task(
        tmp_path / "web" / "seeds" / "book_flight.json",
        instruction="Use the web seed.",
    )
    _write_task(
        tmp_path / "web" / "seeds" / "cua_social_task.json",
        instruction="Use the imported web seed.",
    )

    # Legacy desktop task directories must no longer enter the corpus.
    _write_task(
        tmp_path / "gimp" / "tasks" / "ignored.json",
        instruction="Do not load this GIMP task.",
        task_id="gimp_ignored",
    )
    _write_task(
        tmp_path / "vlc" / "tasks" / "ignored.json",
        instruction="Do not load this VLC task.",
        task_id="vlc_ignored",
    )
    _write_task(
        tmp_path / "travel-ad-hub" / "tasks-web" / "ignored.json",
        instruction="Do not load this legacy web task.",
        task_id="legacy-web-id",
    )

    items = load_surfgym_instructions(tmp_path)

    assert [(item.id, item.text, item.domain) for item in items] == [
        ("gimp_add_border", "Use the GIMP seed.", "gimp"),
        ("vlc_loop_video", "Use the VLC seed.", "vlc"),
        ("book_flight", "Use the web seed.", "chrome"),
        ("cua_social_task", "Use the imported web seed.", "chrome"),
    ]
    assert {item.source for item in items} == {"surfgym"}


def test_load_surfgym_instructions_returns_empty_for_missing_or_empty_roots(tmp_path):
    missing = tmp_path / "missing"
    empty = tmp_path / "empty"
    empty.mkdir()

    assert load_surfgym_instructions(missing) == []
    assert load_surfgym_instructions(empty) == []
