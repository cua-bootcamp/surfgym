from __future__ import annotations

import json
import re
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
    "workspace",
]


type SetupTarget = Literal["desktop", "fixtures"]


class RawSetupFile(FrozenBaseModel):
    source: str
    target: SetupTarget
    source_app: Optional[str] = None

    @model_validator(mode="after")
    def validate_source(self) -> "RawSetupFile":
        _validate_setup_source(self.source)
        if self.source_app is not None:
            _validate_setup_app(self.source_app)
        return self


class RawSetupLaunch(FrozenBaseModel):
    app: str
    source: Optional[str] = None
    args: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_launch(self) -> "RawSetupLaunch":
        _validate_setup_app(self.app)
        if self.source is not None:
            _validate_setup_source(self.source)
        if len(self.args) > 16:
            raise ValueError("setup launch args must be at most 16 safe strings")
        if any(
            not arg
            or len(arg) > 256
            or any(ord(character) < 32 or ord(character) == 127 for character in arg)
            for arg in self.args
        ):
            raise ValueError("setup launch args must be at most 16 safe strings")
        return self


def _validate_setup_source(source: str) -> None:
    path = PurePosixPath(source)
    if (
        not source
        or "\\" in source
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise ValueError("setup file source must be a safe relative POSIX path")


def _validate_setup_app(app: str) -> None:
    if len(app) > 64 or re.fullmatch(r"[a-z0-9][a-z0-9_-]*", app) is None:
        raise ValueError("setup app must be a safe app name")


class RawSeedWebsite(FrozenBaseModel):
    base: str
    param: dict[str, str] = Field(default_factory=dict)
    setup_files: list[RawSetupFile] = Field(default_factory=list)
    open_file: Optional[str] = None
    setup_operations: list[dict[str, JsonValue]] = Field(default_factory=list)
    launches: list[RawSetupLaunch] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, value: object) -> object:
        if isinstance(value, str):
            return {"base": value}

        if isinstance(value, dict) and "launches" in value and not value["launches"]:
            raise ValueError("setup.launches must be a nonempty array")

        return value

    @model_validator(mode="after")
    def validate_setup(self) -> "RawSeedWebsite":
        sources = [item.source for item in self.setup_files]
        if len(sources) != len(set(sources)):
            raise ValueError("setup file sources must be unique")
        destinations = [
            (
                item.target,
                PurePosixPath(item.source).name if item.target == "desktop" else item.source,
            )
            for item in self.setup_files
        ]
        if len(destinations) != len(set(destinations)):
            raise ValueError("duplicate setup destination")
        if self.open_file is not None and self.open_file not in sources:
            raise ValueError("open_file must reference a declared setup file source")
        if self.open_file is not None and self.launches:
            raise ValueError("setup.open_file and setup.launches are mutually exclusive")
        launch_apps = [launch.app for launch in self.launches]
        if len(launch_apps) != len(set(launch_apps)):
            raise ValueError("duplicate setup launch app")
        if any(
            launch.source is not None and launch.source not in sources for launch in self.launches
        ):
            raise ValueError("setup launch source must reference a declared source")
        if (
            self.setup_operations
            and self.setup_files
            and self.open_file is None
            and not self.launches
        ):
            raise ValueError("setup_operations requires open_file or launches")
        return self

    def to_url(self) -> str:
        parsed = urlsplit(self.base)

        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.update(self.param)

        if self.setup_files or self.setup_operations or self.launches:
            setup: dict[str, object] = {}
            if self.setup_files:
                setup["files"] = [
                    item.model_dump(mode="json", exclude_none=True) for item in self.setup_files
                ]
            if self.open_file is not None:
                setup["open_file"] = self.open_file
            if self.setup_operations:
                setup["operations"] = self.setup_operations
            if self.launches:
                setup["launches"] = [
                    item.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
                    for item in self.launches
                ]
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
    source_task_id: Optional[str] = None


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
