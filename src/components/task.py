from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class Website(FrozenBaseModel):
    id: str = "default"
    url: str


class Rule(FrozenBaseModel):
    website_id: str = "default"


class DomRule(Rule):
    match: Literal["contains", "exact", "regex"] = "contains"
    target: Literal["text", "html", "url", "title", "attr"] = "text"
    value: str
    normalize_space: bool = False
    case_sensitive: bool = True

    selector: Optional[str] = None
    attr: Optional[str] = None

    @model_validator(mode="after")
    def validate_shape(self) -> DomRule:
        if self.target == "attr" and not self.attr:
            raise ValueError("attr is required when target='attr'")
        if self.target != "attr" and self.attr is not None:
            raise ValueError("attr is only allowed when target='attr'")
        if self.target in {"url", "title"} and self.selector is not None:
            raise ValueError("selector is not allowed when target is 'url' or 'title'")
        return self


class SpreadsheetRule(Rule):
    cell: str
    value: str


# [WARNING] New rule union elements must be distinguishable by their shape!
RuleUnion = Union[DomRule, SpreadsheetRule]


class Evaluation(FrozenBaseModel):
    mode: Literal["dom", "spreadsheet"] = "dom"
    operator: Literal["or", "and"] = "and"
    rules: list[RuleUnion]

    @field_validator("rules", mode="before")
    @classmethod
    def listify_rule(cls, value: RuleUnion | list[RuleUnion]) -> list[RuleUnion]:
        return value if isinstance(value, list) else [value]

    @model_validator(mode="after")
    def validate_mode_matches_rules(self) -> "Evaluation":
        for rule in self.rules:
            if self.mode == "dom" and not isinstance(rule, DomRule):
                raise ValueError("dom evaluation requires only DomRule")
            if self.mode == "spreadsheet" and not isinstance(rule, SpreadsheetRule):
                raise ValueError("spreadsheet evaluation requires only SpreadsheetRule")
        return self


class Task(FrozenBaseModel):
    task_id: str
    instruction: str
    website: Annotated[list[Website], Field(min_length=1, max_length=4)]
    evaluation: Evaluation

    @field_validator("website", mode="before")
    @classmethod
    def listify_website(
        cls, value: str | list[Website]
    ) -> Annotated[list[Website], Field(min_length=1)]:
        if isinstance(value, str):
            return [Website(url=value)]
        return value


TaskRowsAdapter: TypeAdapter[list[Task]] = TypeAdapter(list[Task])


class TaskStore:
    """Preloaded lookup table for Surfgym tasks."""

    def __init__(self, tasks: list[Task]) -> None:
        self._tasks_by_id: dict[str, Task] = {task.task_id: task for task in tasks}

    @classmethod
    def from_file(cls, path: str | Path) -> "TaskStore":
        return cls(_load_task_rows(Path(path)))

    @classmethod
    def from_rows(cls, rows: list[dict[str, Any]]) -> "TaskStore":
        return cls(TaskRowsAdapter.validate_python(rows))

    def get(self, task_id: str | int) -> Task:
        key = str(task_id)
        if key not in self._tasks_by_id:
            raise KeyError(f"Unknown task_id: {key}")
        return self._tasks_by_id[key].model_copy(deep=True)

    def __contains__(self, task_id: object) -> bool:
        return str(task_id) in self._tasks_by_id

    def __len__(self) -> int:
        return len(self._tasks_by_id)

    def values(self):
        return self._tasks_by_id.values()


def _load_task_rows(path: Path) -> list[Task]:
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    if suffix not in {".json", ".jsonl", ".ndjson"}:
        raise ValueError(f"Unsupported task file type: {path.suffix}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if suffix in {".jsonl", ".ndjson"}:
        payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)

    return TaskRowsAdapter.validate_python(payload)
