from __future__ import annotations

import json
from functools import cached_property
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter
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

    def to_string(self, *, hide_value: bool = False) -> str:
        value = (
            "<hidden>"
            if hide_value
            else json.dumps(
                self.value,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
        return f"{self.cannoncial} = {value}"


type State = list[StateAtom]
type States = Annotated[list[State], Field(min_length=1)]


type Domain = Literal["vlc", "gimp", "impress", "spreadsheet", "word"]


class RawSeedTask(FrozenBaseModel):
    instruction: str
    states: States
    domain: Optional[Domain] = None
    empty_start: Optional[bool] = None
    accumulation: Optional[Accumulation] = None
    website: Optional[str] = None
    setup_file: Optional[str] = None


class SeedTask(FrozenBaseModel):
    website: str
    domain: Domain
    instruction: str
    states: States
    accumulation: Accumulation


type Granularity = Literal["COARSE", "FINE"]
type Accumulation = Literal["DELTA", "CUMULATIVE"]


TaskRowsAdapter: TypeAdapter[list[SeedTask]] = TypeAdapter(list[SeedTask])
HoareStateInstructionRowAdapter: TypeAdapter[dict[str, str]] = TypeAdapter(dict[str, str])
