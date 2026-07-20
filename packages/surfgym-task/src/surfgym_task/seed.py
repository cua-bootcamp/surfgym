from __future__ import annotations

import json
from typing import Annotated, Literal, Optional, TypeAlias, cast

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter
from surfgym_contracts.task import CriteriaCore, JsonValue


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateAtom(CriteriaCore):
    spec: dict[str, JsonValue]

    def to_get(
        self,
    ):
        return f"window.surfgym.get({json.dumps(self.spec, ensure_ascii=False)})"

    def to_set(self):
        spec = json.dumps(self.spec, ensure_ascii=False)
        value = json.dumps(self.value, ensure_ascii=False)
        return f"window.surfgym.set({spec}, {value})"


def listify(value: object) -> list[object]:
    if isinstance(value, list):
        return cast(list[object], value)
    return [value]


State: TypeAlias = Annotated[list[StateAtom], BeforeValidator(listify)]
States: TypeAlias = Annotated[list[State], BeforeValidator(listify), Field(min_length=1)]


Domain: TypeAlias = Literal["vlc", "gimp", "impress", "spreadsheet", "word"]


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


Granularity: TypeAlias = Literal["COARSE", "FINE"]
Accumulation: TypeAlias = Literal["DELTA", "CUMULATIVE"]


TaskRowsAdapter: TypeAdapter[list[SeedTask]] = TypeAdapter(list[SeedTask])
HoareStateInstructionRowAdapter: TypeAdapter[dict[str, str]] = TypeAdapter(dict[str, str])
