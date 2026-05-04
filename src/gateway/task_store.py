from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, TypeAlias, cast

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | dict[str, "JSONValue"] | list["JSONValue"]
JSONObject: TypeAlias = dict[str, JSONValue]


@dataclass
class Task:
    instruction: str
    website: str
    task_id: str
    evaluation: dict[str, Any] | list[Any] | None = None


class TaskStore:
    """Preloaded lookup table for Surfgym tasks."""

    def __init__(self, tasks_by_id: Mapping[str, Task]) -> None:
        self._tasks_by_id = dict(tasks_by_id)

    @classmethod
    def from_file(
        cls,
        path: str | Path,
    ) -> "TaskStore":
        rows = _load_task_rows(Path(path))
        return cls.from_rows(rows)

    @classmethod
    def from_rows(
        cls,
        rows: Iterable[Mapping[str, Any]],
    ) -> "TaskStore":
        tasks_by_id: dict[str, Task] = {}
        for row in rows:
            task = row_to_task(row)
            tasks_by_id[task.task_id] = task
        return cls(tasks_by_id)

    def get(self, task_id: str | int) -> Task:
        key = str(task_id)
        if key not in self._tasks_by_id:
            raise KeyError(f"Unknown task_id: {key}")
        return copy.deepcopy(self._tasks_by_id[key])

    def __contains__(self, task_id: object) -> bool:
        return str(task_id) in self._tasks_by_id

    def __len__(self) -> int:
        return len(self._tasks_by_id)

    def ids(self) -> tuple[str, ...]:
        return tuple(self._tasks_by_id.keys())


def row_to_task(row: Mapping[str, Any]) -> Task:
    task_data = dict(row)
    return Task(
        instruction=task_data["task_name"],
        website=_normalize_website(task_data["website"]),
        task_id=str(task_data["task_id"]),
        evaluation=_extract_evaluation(task_data),
    )


def _load_task_rows(path: Path) -> list[JSONObject]:
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    if suffix in {".json", ".jsonl", ".ndjson"}:
        return _load_json_rows(path)

    raise ValueError(f"Unsupported task file type: {path.suffix}")


def _parse_json_value(text: str) -> JSONValue:
    return cast(JSONValue, json.loads(text))


def _require_json_object(value: JSONValue, *, context: str) -> JSONObject:
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object at {context}, got {type(value).__name__}")
    return value


def _load_json_rows(path: Path) -> list[JSONObject]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    try:
        data = _parse_json_value(text)
    except json.JSONDecodeError:
        return [
            _require_json_object(_parse_json_value(line), context=f"{path}:{line_no}")
            for line_no, line in enumerate(text.splitlines(), start=1)
            if line.strip()
        ]

    if isinstance(data, list):
        return [
            _require_json_object(row, context=f"{path}[{index}]") for index, row in enumerate(data)
        ]

    if isinstance(data, dict):
        tasks = data.get("tasks")
        if isinstance(tasks, list):
            return [
                _require_json_object(row, context=f"{path}.tasks[{index}]")
                for index, row in enumerate(tasks)
            ]
        return [data]

    raise ValueError(f"Unsupported JSON task payload in {path}")


def _normalize_website(website: Any) -> str:
    website_str = str(website)
    if website_str.startswith("http"):
        return website_str
    return f"https://{website_str}"


def _extract_evaluation(task_data: Mapping[str, Any]) -> dict[str, Any] | list[Any] | None:
    evaluation = task_data.get("evaluation")
    if evaluation is None:
        evaluation = task_data.get("rule_evaluation")
    if evaluation is None:
        evaluation = task_data.get("evaluator")

    if isinstance(evaluation, dict):
        return copy.deepcopy(cast(dict[str, Any], evaluation))

    if isinstance(evaluation, list):
        return copy.deepcopy(cast(list[Any], evaluation))

    return None
