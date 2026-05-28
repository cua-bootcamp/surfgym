from __future__ import annotations

import hashlib
import json
from functools import cached_property
from typing import Annotated, Any, Literal, Optional, Protocol, TypeAlias, cast

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter
from surfgym_contracts import RuleCore, TaskCore


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateAtom(RuleCore):
    evalf: str
    applyf: str

    param: Optional[str] = None
    property: list[str] = []
    return_type: Literal["list", "obj"] = "obj"


def listify(value: object) -> list[object]:
    if isinstance(value, list):
        return cast(list[object], value)
    return [value]


# StateAtom converts to a rule
State: TypeAlias = Annotated[list[StateAtom], BeforeValidator(listify)]


# State converts to an evaluation
States: TypeAlias = Annotated[list[State], BeforeValidator(listify), Field(min_length=1)]


class SeedTask(TaskCore):
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


class HoareCreator(Protocol):
    def __call__(
        self,
        states: list[State],
        end: int,
        start: Optional[int] = None,
    ) -> HoareState: ...


class HoareState(FrozenBaseModel):
    start_state: Optional[State] = None
    end_state: State
    complexity: int

    @staticmethod
    def creator(
        accumulation: Accumulation,
    ) -> HoareCreator:
        def accumulate(states: list[State], idx: int) -> State:
            if accumulation == "DELTA":
                return states[idx]

            keep_fresh_state: dict[Any, StateAtom] = {}
            for state in states[: idx + 1]:
                for atom in state:
                    keep_fresh_state[(atom.evalf, atom.param, tuple(atom.property))] = atom

            return list(keep_fresh_state.values())

        def aux(states: list[State], end: int, start: Optional[int] = None) -> HoareState:
            if start is None:
                start_state = None
                complexity = end + 1
            else:
                start_state = accumulate(states, start)
                complexity = end - start

            end_state = accumulate(states, end)
            return HoareState(start_state=start_state, end_state=end_state, complexity=complexity)

        return aux

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
        return hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HoareState):
            return NotImplemented
        return self.key == other.key

    def to_key(self) -> str:
        return self.key


Granularity: TypeAlias = Literal["COARSE", "FINE"]
Accumulation: TypeAlias = Literal["DELTA", "CUMULATIVE"]


TaskRowsAdapter: TypeAdapter[list[SeedTask]] = TypeAdapter(list[SeedTask])
HoareStateInstructionRowAdapter: TypeAdapter[dict[str, str]] = TypeAdapter(dict[str, str])
