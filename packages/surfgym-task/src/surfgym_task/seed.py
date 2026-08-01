from __future__ import annotations

import json
from functools import cached_property
from typing import Annotated, Literal, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, model_validator
from surfgym_contracts.task import ConsoleCriteria, CriteriaCore


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateAtom(CriteriaCore):
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


type State = list[StateAtom]
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


class RawSeedTask(FrozenBaseModel):
    instruction: str
    states: States
    website: RawSeedWebsite
    domain: Optional[Domain] = None
    empty_start: Optional[bool] = None
    accumulation: Optional[Accumulation] = None


class SeedTask(FrozenBaseModel):
    website: str
    domain: Domain
    instruction: str
    states: States
    accumulation: Accumulation


type Granularity = Literal["COARSE", "FINE"]
type Accumulation = Literal["DELTA", "CUMULATIVE"]
type Profile = Literal["ROLLOUT", "SNAPSHOT"]

TaskRowsAdapter: TypeAdapter[list[SeedTask]] = TypeAdapter(list[SeedTask])
HoareStateInstructionRowAdapter: TypeAdapter[dict[str, str]] = TypeAdapter(dict[str, str])
