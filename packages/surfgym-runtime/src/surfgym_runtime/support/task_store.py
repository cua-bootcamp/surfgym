import json
from pathlib import Path
from typing import cast

import json5
from surfgym_contracts.task import Task, TaskRowsAdapter


class TaskStore:
    """Preloaded lookup table for Surfgym tasks."""

    def __init__(self, tasks: list[Task]) -> None:
        self._tasks_by_id: dict[str, Task] = {task.task_id: task for task in tasks}

    @classmethod
    def from_file(cls, path: str | Path) -> "TaskStore":
        return cls(_load_task_rows(Path(path)))

    @classmethod
    def from_rows(cls, rows: list[dict[str, object]]) -> "TaskStore":
        return cls(TaskRowsAdapter.validate_python(rows))

    def get(self, task_id: str | int) -> Task | None:
        key = str(task_id)
        return self._tasks_by_id.get(key)

    def __contains__(self, task_id: object) -> bool:
        return str(task_id) in self._tasks_by_id

    def __len__(self) -> int:
        return len(self._tasks_by_id)

    def all_tasks(self):
        return list(self._tasks_by_id.values())


def _load_task_rows(path: Path) -> list[Task]:
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    if suffix not in {".json", ".jsonl", ".ndjson", ".jsonc"}:
        raise ValueError(f"Unsupported task file type: {path.suffix}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if suffix in {".jsonl", ".ndjson"}:
        payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif suffix == ".jsonc":
        payload = cast(object, json5.loads(text))
    else:
        payload = json.loads(text)

    return TaskRowsAdapter.validate_python(payload)
