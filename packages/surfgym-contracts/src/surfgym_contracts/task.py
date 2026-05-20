from collections.abc import Sequence
from typing import Annotated, Literal, Optional, TypeAlias, Union

from pydantic import (
    BaseModel,
    BeforeValidator,
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


class _WebsiteDependent(FrozenBaseModel):
    website_id: str = "_"


class Website(_WebsiteDependent):
    url: str


Value: TypeAlias = Union[str, int, float, bool]


class RuleCore(_WebsiteDependent):
    match: Literal["contains", "exact", "regex"] = "contains"
    normalize_space: bool = False
    case_sensitive: bool = True
    value: Value


class ConsoleRule(RuleCore):
    mode: Literal["console"] = "console"
    script: str


class DomRule(RuleCore):
    mode: Literal["dom"] = "dom"
    target: Literal["text", "html", "url", "title", "attr"] = "text"
    selector: Optional[str] = None
    attr: Optional[str] = None

    @model_validator(mode="after")
    def validate_shape(self) -> "DomRule": ...


def fill_rule_mode(value: object) -> object:
    if not isinstance(value, dict) or "mode" in value:
        return value  # pyright: ignore[reportUnknownVariableType]

    if "script" in value:
        return {**value, "mode": "console"}  # pyright: ignore[reportUnknownVariableType]
    return {**value, "mode": "dom"}  # pyright: ignore[reportUnknownVariableType]


Rule = Annotated[
    Union[DomRule, ConsoleRule],
    Field(discriminator="mode"),
    BeforeValidator(fill_rule_mode),
]


class Evaluation(FrozenBaseModel):
    operator: Literal["or", "and"] = "and"
    rules: Sequence[Rule]

    @field_validator("rules", mode="before")
    @classmethod
    def listify_rule(cls, value: Rule | list[Rule]) -> list[Rule]:
        return value if isinstance(value, list) else [value]


class Action(_WebsiteDependent):
    mode: Literal["console", "playwright"] = "console"
    script: str


class TaskCore(FrozenBaseModel):
    task_id: str
    instruction: str
    website: Annotated[list[Website], Field(min_length=1, max_length=4)]

    @field_validator("website", mode="before")
    @classmethod
    def listify_website(
        cls, value: str | list[Website]
    ) -> Annotated[list[Website], Field(min_length=1)]:
        if isinstance(value, str):
            return [Website(url=value)]
        return value


class Task(TaskCore):
    evaluation: Evaluation
    complexity: int

    setup: Optional[list[Action]] = None
    transition: Optional[list[Action]] = None

    @field_validator("setup", "transition", mode="before")
    @classmethod
    def listify_actions(cls, value: None | Action | list[Action]) -> Optional[list[Action]]:
        if value is None:
            return None
        if isinstance(value, Action):
            return [value]
        return value


TaskRowsAdapter: TypeAdapter[list[Task]] = TypeAdapter(list[Task])

Observation: TypeAlias = Optional[Value]
