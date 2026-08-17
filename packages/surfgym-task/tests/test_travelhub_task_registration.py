from pathlib import Path

from surfgym_task.web import WEB_STATE_RESET_HOOK, load_web_tasks


def test_travelhub_json_corpus_registers_without_building_a_database():
    data_dir = (
        Path(__file__).parents[1]
        / "src"
        / "surfgym_task"
        / "data"
        / "travel-ad-hub"
    )

    tasks = load_web_tasks(data_dir / "tasks-web")

    assert len(tasks) == 36
    assert len({task.task_id for task in tasks}) == 36
    assert all(task.website[0].url.startswith("http://localhost:3200/") for task in tasks)
    assert all(WEB_STATE_RESET_HOOK in task.lifecycle_hooks.release for task in tasks)
    assert len([task for task in tasks if task.lifecycle_hooks.allocate]) == 3
    assert not (data_dir / "out" / "tasks.sqlite3").exists()
