import hashlib
import json
from functools import cached_property
from typing import Any, Iterator

from pydantic import BaseModel, ConfigDict

from surfgym_task.seed import Accumulation, Granularity, SeedTask, State, StateAtom, States


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class HoareState(FrozenBaseModel):
    origin_start_idx: int
    origin_end_idx: int
    start_state: State
    end_state: State
    complexity: int

    @cached_property
    def canonical_payload(self) -> dict[str, Any]:
        return {
            "startState": _canonical_state(self.start_state),
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


class HoareStateGenerator:
    def __init__(self, granularity: Granularity):
        self.granularity = granularity

    def generate(self, seed: SeedTask) -> Iterator[HoareState]:
        for start_idx, end_idx in self._iter_windows(seed):
            yield self._build_hoare_state(seed.states, start_idx, end_idx, seed.accumulation)

    def _iter_windows(self, seed: SeedTask) -> Iterator[tuple[int, int]]:
        for end_idx in range(1, len(seed.states)):
            if self.granularity == "COARSE":
                yield (0, end_idx)

            elif self.granularity == "FINE":
                for start_idx in range(end_idx):
                    yield (start_idx, end_idx)

    def _build_hoare_state(
        self, states: States, start_idx: int, end_idx: int, accumulation: Accumulation
    ) -> HoareState:
        start_state = self._accumulate(
            states,
            start_idx,
            accumulation,
        )
        end_state = self._accumulate(states, end_idx, accumulation)

        return HoareState(
            origin_start_idx=start_idx,
            origin_end_idx=end_idx,
            start_state=start_state,
            end_state=end_state,
            complexity=end_idx - start_idx,
        )

    def _accumulate(
        self,
        states: States,
        idx: int,
        accumulation: Accumulation,
    ) -> State:
        if accumulation == "DELTA":
            return states[idx]

        keep_fresh_state: dict[str, StateAtom] = {}
        for state in states[: idx + 1]:
            for atom in state:
                keep_fresh_state[_canonical_json(atom.identity_payload())] = atom

        return list(keep_fresh_state.values())


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
