from __future__ import annotations

import json
from functools import cached_property
from pathlib import PurePosixPath
from typing import Annotated, Literal, Optional, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)
from surfgym_contracts.task import (
    ConsoleCriteria,
    CriteriaCore,
    CriteriaEvaluation,
    InfeasibleEvaluation,
    LLMJudgeEvaluation,
)


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateAtom(CriteriaCore):
    """
    Converted into a single `ConsoleCriteria`.
    """

    spec: dict[str, JsonValue]

    @cached_property
    def cannoncial(self) -> str:
        return json.dumps(
            self.spec,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def to_get(
        self,
    ):
        return f"window.surfgym.get({json.dumps(self.spec, ensure_ascii=False)})"

    def to_set(self):
        spec = json.dumps(self.spec, ensure_ascii=False)
        value = json.dumps(self.value, ensure_ascii=False)
        return f"window.surfgym.set({spec}, {value})"

    def to_console_criteria(self) -> ConsoleCriteria:
        return ConsoleCriteria(
            value=self.value,
            match=self.match,
            normalize_space=self.normalize_space,
            case_sensitive=self.case_sensitive,
            script=self.to_get(),
        )


class State(FrozenBaseModel):
    atoms: list[StateAtom]

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, value: object) -> object:
        if isinstance(value, list):
            atoms = cast(list[object], value)
            return {"atoms": atoms}
        return value

    def to_criteria_evaluation(self) -> CriteriaEvaluation:
        if not self.atoms:
            raise ValueError("Cannot evaluate an empty state.")

        return CriteriaEvaluation(
            operator="and",
            criteria=[atom.to_console_criteria() for atom in self.atoms],
        )


type States = Annotated[list[State], Field(min_length=1)]
type InitialStates = Annotated[list[State], Field(min_length=1, max_length=1)]


type Domain = Literal[
    "chrome",
    "vlc",
    "gimp",
    "impress",
    "spreadsheet",
    "word",
    "vscode",
    "web",
]


type SetupTarget = Literal["desktop", "fixtures"]


class RawSetupFile(FrozenBaseModel):
    source: str
    target: SetupTarget

    @model_validator(mode="after")
    def validate_source(self) -> "RawSetupFile":
        path = PurePosixPath(self.source)
        if (
            not self.source
            or "\\" in self.source
            or path.is_absolute()
            or any(part in ("", ".", "..") for part in path.parts)
        ):
            raise ValueError("setup file source must be a safe relative POSIX path")
        return self


class RawSeedWebsite(FrozenBaseModel):
    base: str
    param: dict[str, str] = Field(default_factory=dict)
    setup_files: list[RawSetupFile] = Field(default_factory=list)
    open_file: Optional[str] = None
    setup_operations: list[dict[str, JsonValue]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, value: object) -> object:
        if isinstance(value, str):
            return {"base": value}

        return value

    @model_validator(mode="after")
    def validate_setup(self) -> "RawSeedWebsite":
        sources = [item.source for item in self.setup_files]
        if len(sources) != len(set(sources)):
            raise ValueError("setup file sources must be unique")
        if self.open_file is not None and self.open_file not in sources:
            raise ValueError("open_file must reference a declared setup file source")
        if self.setup_operations and self.setup_files and self.open_file is None:
            raise ValueError("setup_operations requires open_file")
        return self

    def to_url(self) -> str:
        parsed = urlsplit(self.base)

        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.update(self.param)

        if self.setup_files or self.setup_operations:
            setup: dict[str, JsonValue] = {}
            if self.setup_files:
                setup["files"] = [
                    item.model_dump(mode="json") for item in self.setup_files
                ]
            if self.open_file is not None:
                setup["open_file"] = self.open_file
            if self.setup_operations:
                setup["operations"] = self.setup_operations
            query["setup"] = json.dumps(
                setup,
                ensure_ascii=False,
                separators=(",", ":"),
            )

        return urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(query),
                parsed.fragment,
            )
        )


class _RawSeedTask(FrozenBaseModel):
    instruction: str
    website: RawSeedWebsite
    domain: Optional[Domain] = None


class RawLLMJudgeSeedTask(_RawSeedTask):
    evaluation: LLMJudgeEvaluation


class RawInfeasibleSeedTask(_RawSeedTask):
    evaluation: InfeasibleEvaluation
    states: Optional[InitialStates] = None


class RawCriteriaSeedTask(_RawSeedTask):
    states: States
    empty_start: Optional[bool] = None
    accumulation: Optional[Accumulation] = None


type RawSeedTask = RawCriteriaSeedTask | RawLLMJudgeSeedTask | RawInfeasibleSeedTask


class _SeedTask(FrozenBaseModel):
    website: str
    domain: Domain
    instruction: str


class LLMJudgeSeedTask(_SeedTask):
    evaluation: LLMJudgeEvaluation


class InfeasibleSeedTask(_SeedTask):
    evaluation: InfeasibleEvaluation
    states: Optional[InitialStates] = None


class CriteriaSeedTask(_SeedTask):
    states: States
    accumulation: Accumulation


type SeedTask = CriteriaSeedTask | LLMJudgeSeedTask | InfeasibleSeedTask


type Granularity = Literal["COARSE", "FINE"]
type Accumulation = Literal["DELTA", "CUMULATIVE"]
type Profile = Literal["ROLLOUT", "SNAPSHOT"]
