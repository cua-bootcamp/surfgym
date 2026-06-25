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
    model_validator,
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


class Website(_WebsiteDependent):
    url: str


ScalarValue: TypeAlias = Union[str, int, float, bool]
Value: TypeAlias = Union[ScalarValue, list[str]]


class RuleCore(_WebsiteDependent):
    match: Literal["contains", "exact", "regex"] = "exact"
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


class ChromiumRule(RuleCore):
    mode: Literal["chromium"] = "chromium"
    type: Literal[
        "json_value",
        "active_url",
        "open_tabs",
        "bookmark_bar_folder",
        "bookmark_bar_url",
        "history_keyword_absent",
        "cookie_domain_absent",
    ] = "json_value"
    file: Optional[str] = None
    path: Optional[str] = None
    query: Optional[str] = None
    domain: Optional[str] = None

    @model_validator(mode="after")
    def validate_chromium_rule(self):
        if self.type == "json_value":
            if self.file is None or self.path is None:
                raise ValueError("Chromium json_value rules require file and path.")
            if self.query is not None or self.domain is not None:
                raise ValueError("Chromium json_value rules do not accept query or domain.")
            if isinstance(self.value, list):
                raise ValueError("Chromium json_value rules require a scalar value.")
            return self

        if self.file is not None or self.path is not None:
            raise ValueError("Only Chromium json_value rules accept file and path.")

        if self.type == "history_keyword_absent":
            if not self.query:
                raise ValueError("Chromium history_keyword_absent rules require query.")
            if not isinstance(self.value, bool):
                raise ValueError("Chromium history_keyword_absent rules require a boolean value.")
            return self

        if self.type == "cookie_domain_absent":
            if not self.domain:
                raise ValueError("Chromium cookie_domain_absent rules require domain.")
            if not isinstance(self.value, bool):
                raise ValueError("Chromium cookie_domain_absent rules require a boolean value.")
            return self

        if self.query is not None or self.domain is not None:
            raise ValueError(
                "Only Chromium history_keyword_absent and cookie_domain_absent rules accept "
                "query or domain."
            )

        if self.type == "open_tabs":
            if not isinstance(self.value, list):
                raise ValueError("Chromium open_tabs rules require a list value.")
            return self

        if isinstance(self.value, list):
            raise ValueError(f"Chromium {self.type} rules require a scalar value.")
        return self


def fill_rule_mode(value: object) -> object:
    if not isinstance(value, dict) or "mode" in value:
        return value  # pyright: ignore[reportUnknownVariableType]

    if "script" in value:
        return {**value, "mode": "console"}  # pyright: ignore[reportUnknownVariableType]
    if "file" in value and "path" in value:
        return {**value, "mode": "chromium"}  # pyright: ignore[reportUnknownVariableType]
    if value.get("type") in {
        "active_url",
        "open_tabs",
        "bookmark_bar_folder",
        "bookmark_bar_url",
        "history_keyword_absent",
        "cookie_domain_absent",
    }:
        return {**value, "mode": "chromium"}  # pyright: ignore[reportUnknownVariableType]
    return {**value, "mode": "dom"}  # pyright: ignore[reportUnknownVariableType]


Rule = Annotated[
    Union[DomRule, ConsoleRule, ChromiumRule],
    Field(discriminator="mode"),
    BeforeValidator(fill_rule_mode),
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


class ProfileJsonValue(FrozenBaseModel):
    file: str
    path: str
    value: ScalarValue


class ProfileHistoryEntry(FrozenBaseModel):
    url: str
    title: str = ""


class ProfileCookie(FrozenBaseModel):
    url: str
    name: str
    value: str
    domain: Optional[str] = None
    path: str = "/"
    expires: Optional[float] = None
    http_only: bool = False
    secure: bool = False
    same_site: Optional[Literal["Strict", "Lax", "None"]] = None


class ProfileSetup(FrozenBaseModel):
    json_values: list[ProfileJsonValue] = []
    history_entries: list[ProfileHistoryEntry] = []
    cookies: list[ProfileCookie] = []


class Task(TaskCore):
    hash: str
    evaluation: Evaluation
    complexity: int

    setup: Optional[list[Action]] = None
    transition: Optional[list[Action]] = None

    profile_setup: Optional[ProfileSetup] = None

    @field_validator("setup", "transition", mode="before")
    @classmethod
    def listify_actions(cls, value: None | Action | list[Action]) -> Optional[list[Action]]:
        if value is None:
            return None
        if isinstance(value, Action):
            return [value]
        return value


TaskRowsAdapter: TypeAdapter[list[Task]] = TypeAdapter(list[Task])
