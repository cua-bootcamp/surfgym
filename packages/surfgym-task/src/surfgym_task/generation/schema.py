from __future__ import annotations

import hashlib
import json
from functools import cached_property
from typing import Annotated, Any, Literal, Optional, TypeAlias, Union, cast

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class _StateAtom(FrozenBaseModel):
    match: Literal["contains", "exact", "regex"] = "contains"
    normalize_space: bool = False
    case_sensitive: bool = True

    param: Optional[str] = None
    property: list[str] = []
    value: str | int | float | bool
    return_type: Literal["list", "obj"] = "obj"


class SpreadsheetStateAtom(_StateAtom):
    f: Literal["getCellMeta"]


class WordStateAtom(_StateAtom):
    f: Literal[
        "word-text-style",
        "word-body",
        "word-paragraph",
        "word-infeasible",
        "word-document",
        "word-table",
        "word-footer",
    ]


class ProzillaStateAtom(_StateAtom):
    f: Literal[
        'prozilla["file-explorer"]',
        'prozilla["text-editor"]',
        'prozilla["media-viewer"]',
        'prozilla["filetree"]',
        'prozilla["settings"]',
        'prozilla["modal"]',
        'prozilla["taskbar"]',
        'prozilla["commands"]',
    ]


StateAtomPayload: TypeAlias = Union[
    SpreadsheetStateAtom,
    ProzillaStateAtom,
    WordStateAtom,
]

StateAtom: TypeAlias = Annotated[
    StateAtomPayload,
    Field(discriminator="f"),
]


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return cast(list[object], value)
    return [value]


# StateAtom converts to a rule
State: TypeAlias = Annotated[list[StateAtom], BeforeValidator(_as_list)]


# State converts to an evaluation
States: TypeAlias = Annotated[list[State], BeforeValidator(_as_list), Field(min_length=1)]


class SeedTask(FrozenBaseModel):
    task_id: str
    instruction: str
    website: str
    states: States


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _canonical_state(state: State) -> list[dict[str, Any]]:
    atoms = [atom.model_dump(mode="json") for atom in state]
    return sorted(atoms, key=_canonical_json)


class HoareState(FrozenBaseModel):
    start_state: Optional[State] = None
    end_state: State
    complexity: int

    @cached_property
    def canonical_payload(self) -> dict[str, Any]:
        return {
            "startState": (
                None if self.start_state is None else _canonical_state(self.start_state)
            ),
            "endState": _canonical_state(self.end_state),
        }

    @cached_property
    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_payload)

    @cached_property
    def key(self) -> str:
        digest = hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()
        return f"hoare:v1:{digest}"

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HoareState):
            return NotImplemented
        return self.key == other.key

    def to_key(self) -> str:
        return self.key


Granularity: TypeAlias = Literal["COARSE", "FINE"]
State_Scope: TypeAlias = Literal["DELTA", "CUMULATIVE"]


TaskRowsAdapter: TypeAdapter[list[SeedTask]] = TypeAdapter(list[SeedTask])
HoareStateInstructionRowAdapter: TypeAdapter[dict[str, str]] = TypeAdapter(dict[str, str])
