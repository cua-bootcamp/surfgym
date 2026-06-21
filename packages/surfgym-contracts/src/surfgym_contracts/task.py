from collections.abc import Sequence
from typing import Annotated, Literal, Mapping, Optional, TypeAlias, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    TypeAdapter,
    field_validator,
)

################################
#          Auto Infer          #
################################


def infer_rule_mode(value: object) -> Optional[str]:
    if isinstance(value, Mapping):
        if "mode" in value and isinstance(value["mode"], str):
            return value["mode"]
        return "console" if "script" in value else "dom"


def infer_evaluation_mode(value: object) -> Optional[str]:
    if isinstance(value, Mapping):
        if "mode" in value and isinstance(value["mode"], str):
            return value["mode"]
        return "llm" if "model" in value else "rule"


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


################################
#             Rule             #
################################


class _WebsiteDependent(FrozenBaseModel):
    website_id: str = "_"


Value: TypeAlias = Union[str, int, float, bool]
Observation: TypeAlias = Optional[Value]


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


Rule = Annotated[
    Union[
        Annotated[DomRule, Tag("dom")],
        Annotated[ConsoleRule, Tag("console")],
    ],
    Discriminator(infer_rule_mode),
]


################################
#          Evaluation          #
################################


class RuleBasedEvaluation(FrozenBaseModel):
    mode: Literal["rule"] = "rule"
    operator: Literal["or", "and"] = "and"
    rules: Sequence[Rule]

    @field_validator("rules", mode="before")
    @classmethod
    def listify_rule(cls, value: Rule | list[Rule]) -> list[Rule]:
        return value if isinstance(value, list) else [value]


ExternalApp: TypeAlias = Literal["impress", "gimp", "vlc"]


class LLMJudgeEvaluation(FrozenBaseModel):
    mode: Literal["llm"] = "llm"
    external_app: ExternalApp
    model: str = "gpt-5.4-mini"
    image_detail: Literal["low", "high", "auto"] = "high"
    max_frames: int = Field(default=12, ge=2)


Evaluation = Annotated[
    Union[
        Annotated[RuleBasedEvaluation, Tag("rule")],
        Annotated[LLMJudgeEvaluation, Tag("llm")],
    ],
    Discriminator(infer_evaluation_mode),
]


################################
#             Task             #
################################


class Website(_WebsiteDependent):
    url: str


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
    hash: str
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
