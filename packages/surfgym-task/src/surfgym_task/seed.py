from __future__ import annotations

import json
from typing import Annotated, Literal, Optional, TypeAlias, cast

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, JsonValue, TypeAdapter
from surfgym_contracts.task import ConsoleCriteria, CriteriaCore


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateAtom(CriteriaCore):
    query: list[tuple[str, JsonValue]]
    path: list[str | int]

    def to_script(self, type: Literal["eval", "action"]) -> str:
        payload = {"query": self.query, "path": self.path, "value": self.value}
        f = "get" if type == "eval" else "set"
        return f"""
(() => {{
    return window.surfgym.{f}({json.dumps(payload, ensure_ascii=False)})
}})()
""".strip()

    def to_console_criteria(self) -> ConsoleCriteria:
        return ConsoleCriteria(
            value=self.value,
            match=self.match,
            normalize_space=self.normalize_space,
            case_sensitive=self.case_sensitive,
            script=self.to_script(type="eval"),
        )

    def to_string(self, hide_value: bool = False) -> str:
        query = self._query_string()
        path = self._path_string()
        value = "<hidden>" if hide_value else json.dumps(self.value, ensure_ascii=False)
        return f"{query}{path} = {value}"

    def _query_string(self) -> str:
        return "".join(
            f"{name}({'' if value is None else json.dumps(value, ensure_ascii=False)})"
            for name, value in self.query
        )

    def _path_string(self) -> str:
        return "".join(f".{p}" if isinstance(p, str) else f"[{p}]" for p in self.path)


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
