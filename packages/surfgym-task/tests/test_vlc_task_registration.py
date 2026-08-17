from pathlib import Path

from surfgym_task.web import (
    DOCKER_FIXTURE_RELEASE_HOOK,
    WEB_STATE_RESET_HOOK,
    load_fixture_tasks,
)


def test_vlc_json_corpus_registers_without_building_a_database():
    data_dir = (
        Path(__file__).parents[1]
        / "src"
        / "surfgym_task"
        / "data"
        / "vlc"
    )

    tasks = load_fixture_tasks(data_dir / "tasks")

    assert len(tasks) == 48
    assert len({task.task_id for task in tasks}) == 48
    assert all(
        task.website[0].url.startswith("http://localhost:53001/vlc")
        for task in tasks
    )
    assert all(
        DOCKER_FIXTURE_RELEASE_HOOK in task.lifecycle_hooks.release
        for task in tasks
    )
    assert all(
        WEB_STATE_RESET_HOOK not in task.lifecycle_hooks.release for task in tasks
    )
    assert not (data_dir / "out" / "tasks.sqlite3").exists()
