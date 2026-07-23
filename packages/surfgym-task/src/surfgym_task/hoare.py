import hashlib
import json
from functools import cached_property
from typing import Iterator

from pydantic import BaseModel, ConfigDict

from surfgym_task.seed import Accumulation, Granularity, SeedTask, State, StateAtom, States


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class HoareState(FrozenBaseModel):
    origin_start_idx: int
    origin_end_idx: int
    start_state: State
    end_state: State

    @cached_property
    def complexity(self) -> int:
        return self.origin_end_idx - self.origin_start_idx

    @cached_property
    def cannoncial(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )

    @cached_property
    def hash(self) -> str:
        return hashlib.sha256(self.cannoncial.encode("utf-8")).hexdigest()

    @cached_property
    def diff(self) -> State:
        start_by_target = {atom.cannoncial: atom for atom in self.start_state}
        return [
            end_atom
            for end_atom in self.end_state
            if start_by_target.get(end_atom.cannoncial) != end_atom
        ]


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
                keep_fresh_state[atom.cannoncial] = atom

        return list(keep_fresh_state.values())
