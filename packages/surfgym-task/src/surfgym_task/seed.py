from __future__ import annotations

import json
from functools import cached_property
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


type Domain = Literal["vlc", "gimp", "impress", "spreadsheet", "word"]


class RawSeedWebsite(FrozenBaseModel):
    base: str
    param: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, value: object) -> object:
        if isinstance(value, str):
            return {"base": value}

        return value

    def to_url(self) -> str:
        parsed = urlsplit(self.base)

        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.update(self.param)

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


class RawCriteriaSeedTask(_RawSeedTask):
    states: States
    empty_start: Optional[bool] = None
    accumulation: Optional[Accumulation] = None


type RawSeedTask = RawCriteriaSeedTask | RawLLMJudgeSeedTask


class _SeedTask(FrozenBaseModel):
    website: str
    domain: Domain
    instruction: str


class LLMJudgeSeedTask(_SeedTask):
    evaluation: LLMJudgeEvaluation


class CriteriaSeedTask(_SeedTask):
    states: States
    accumulation: Accumulation


type SeedTask = CriteriaSeedTask | LLMJudgeSeedTask


type Granularity = Literal["COARSE", "FINE"]
type Accumulation = Literal["DELTA", "CUMULATIVE"]
type Profile = Literal["ROLLOUT", "SNAPSHOT"]
