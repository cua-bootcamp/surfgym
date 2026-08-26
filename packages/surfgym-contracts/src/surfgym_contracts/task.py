from typing import Annotated, Literal, Mapping, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    TypeAdapter,
    field_validator,
    model_validator,
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


################################
#             Rule             #
################################


class _WebsiteDependent(FrozenBaseModel):
    website_id: str = "_"


type Value = None | str | bool | int | float | list[Value] | dict[str, Value]
type Observation = Optional[Value]
type MatchMode = Literal["contains", "exact", "regex"]


class CriteriaCore(_WebsiteDependent):
    match: MatchMode = "exact"
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


class CuaStateSource(_WebsiteDependent):
    """Browser state captured from one direct CUA web application."""

    app_base: str
    sid: str
    current_state_key: str
    initial_state_key: str


class CuaEvaluation(FrozenBaseModel):
    """Evaluate a CUA-Gym task against privileged browser-state snapshots."""

    mode: Literal["cua"] = "cua"
    source_task_id: str
    reward_script: str
    states: Annotated[list[CuaStateSource], Field(min_length=1, max_length=4)]


class InfeasibleEvaluation(FrozenBaseModel):
    """Evaluate whether an infeasible task was explicitly failed."""

    mode: Literal["infeasible"] = "infeasible"


Evaluation = Annotated[
    Union[
        Annotated[CriteriaEvaluation, Tag("criteria")],
        Annotated[LLMJudgeEvaluation, Tag("llm")],
        Annotated[CuaEvaluation, Tag("cua")],
        Annotated[InfeasibleEvaluation, Tag("infeasible")],
    ],
    Discriminator(infer_evaluation()),
]


################################
#             Task             #
################################


class Website(_WebsiteDependent):
    url: str


class Hook(_WebsiteDependent):
    timing: Literal["before", "after"]
    script: str


class LifecycleHooks(FrozenBaseModel):
    allocate: list[Hook] = []
    observe: list[Hook] = []
    release: list[Hook] = []


class Task(FrozenBaseModel):
    task_id: str
    instruction: str
    website: Annotated[list[Website], Field(min_length=1, max_length=4)]

    evaluation: Evaluation
    complexity: Optional[int] = None
    lifecycle_hooks: LifecycleHooks = LifecycleHooks()

    include_reward_image: bool = False

    @field_validator("website", mode="before")
    @classmethod
    def listify_website(
        cls, value: str | list[Website]
    ) -> Annotated[list[Website], Field(min_length=1)]:
        if isinstance(value, str):
            return [Website(url=value)]
        return value

    @model_validator(mode="after")
    def validate_website_references(self) -> "Task":
        website_ids = [website.website_id for website in self.website]
        duplicate_ids = sorted(
            {website_id for website_id in website_ids if website_ids.count(website_id) > 1}
        )
        if duplicate_ids:
            raise ValueError(f"website_id values must be unique: {duplicate_ids}")

        referenced_ids = {
            hook.website_id
            for hooks in (
                self.lifecycle_hooks.allocate,
                self.lifecycle_hooks.observe,
                self.lifecycle_hooks.release,
            )
            for hook in hooks
        }
        match self.evaluation:
            case CriteriaEvaluation():
                referenced_ids.update(
                    criterion.website_id for criterion in self.evaluation.criteria
                )
            case CuaEvaluation():
                referenced_ids.update(state.website_id for state in self.evaluation.states)

        unknown_ids = sorted(referenced_ids - set(website_ids))
        if unknown_ids:
            raise ValueError(f"website_id references must name a website: {unknown_ids}")

        return self


TaskRowsAdapter: TypeAdapter[list[Task]] = TypeAdapter(list[Task])
