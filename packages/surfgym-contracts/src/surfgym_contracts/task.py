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


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


#################################
#     Mode Inference Helper     #
#################################


def infer_mode(key_tags: Mapping[str, str], *, default: Optional[str] = None):
    def infer_by_rule(value: object) -> Optional[str]:
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="python")

        if not isinstance(value, Mapping):
            return None

        if "mode" in value and isinstance(value["mode"], str):
            return value["mode"]

        for key, tag in key_tags.items():
            if key in value:
                return tag

        return default

    return infer_by_rule


def infer_criteria():
    return infer_mode({"script": "console"}, default="dom")


def infer_evaluation():
    return infer_mode({"criteria": "criteria"}, default="llm")


def infer_hook():
    return infer_mode({"method": "api", "script": "console"}, default="console")


################################
#             Rule             #
################################


class _WebsiteDependent(FrozenBaseModel):
    website_id: str = "_"


ScalarValue: TypeAlias = Union[str, int, float, bool]
Value: TypeAlias = Union[ScalarValue, list[str]]
Observation: TypeAlias = Optional[Value]


class CriteriaCore(_WebsiteDependent):
    match: Literal["contains", "exact", "regex"] = "exact"
    normalize_space: bool = False
    case_sensitive: bool = True
    value: Value


class ConsoleCriteria(CriteriaCore):
    mode: Literal["console"] = "console"
    script: str


class DomCriteria(CriteriaCore):
    mode: Literal["dom"] = "dom"
    target: Literal["text", "html", "url", "title", "attr"] = "text"
    selector: Optional[str] = None
    attr: Optional[str] = None


Criteria = Annotated[
    Union[
        Annotated[DomCriteria, Tag("dom")],
        Annotated[ConsoleCriteria, Tag("console")],
    ],
    Discriminator(infer_criteria()),
]


################################
#          Evaluation          #
################################


class CriteriaEvaluation(FrozenBaseModel):
    mode: Literal["criteria"] = "criteria"
    operator: Literal["or", "and"] = "and"
    criteria: list[Criteria]

    @field_validator("criteria", mode="before")
    @classmethod
    def listify_criteria(cls, value: Criteria | list[Criteria]) -> list[Criteria]:
        return value if isinstance(value, list) else [value]


class LLMJudgeEvaluation(FrozenBaseModel):
    mode: Literal["llm"] = "llm"
    model: str = "gpt-5.4-mini"
    image_detail: Literal["low", "high", "auto"] = "high"
    max_frames: int = Field(default=12, ge=2)


Evaluation = Annotated[
    Union[
        Annotated[CriteriaEvaluation, Tag("criteria")],
        Annotated[LLMJudgeEvaluation, Tag("llm")],
    ],
    Discriminator(infer_evaluation()),
]


################################
#             Task             #
################################


class Website(_WebsiteDependent):
    url: str


class _Hook(_WebsiteDependent):
    timing: Literal["before", "after", "replace"]


class ConsoleHook(_Hook):
    mode: Literal["console"] = "console"
    script: str


class ApiHook(_Hook):
    mode: Literal["api"] = "api"
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    url: str
    json_payload: Optional[dict[str, object]] = None


Hook: TypeAlias = Annotated[
    Union[
        Annotated[ConsoleHook, Tag("console")],
        Annotated[ApiHook, Tag("api")],
    ],
    Discriminator(infer_hook()),
]


class LifecycleHooks(FrozenBaseModel):
    allocate: list[Hook] = []
    evaluate: list[Hook] = []
    release: list[Hook] = []
    reference: list[Hook] = []


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

    lifecycle_hooks: LifecycleHooks = LifecycleHooks()


TaskRowsAdapter: TypeAdapter[list[Task]] = TypeAdapter(list[Task])
