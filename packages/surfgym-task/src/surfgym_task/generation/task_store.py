import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator, TypeVar, cast

import json5
from pydantic import TypeAdapter

from surfgym_task.generation.instruction_generator import InstructionGenerator
from surfgym_task.generation.schema import (
    Granularity,
    HoareState,
    HoareStateInstructionRowAdapter,
    SeedTask,
    State,
    State_Scope,
    StateAtom,
    TaskRowsAdapter,
)

T = TypeVar("T")


class TaskStore:
    def __init__(
        self,
        seed_dir: Path,
        granularity: Granularity = "COARSE",
        state_scope: State_Scope = "DELTA",
    ) -> None:
        self.granularity: Granularity = granularity
        self.state_scope: State_Scope = state_scope
        self.instruction_generator = InstructionGenerator()

        self.seed_path = seed_dir / "seed.jsonc"
        self.instruction_path = seed_dir / "instruction.jsonc"
        self.output_dir = seed_dir / "out"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.seed_tasks: list[SeedTask] = load_rows(self.seed_path, TaskRowsAdapter)
        try:
            self.hash_to_inst = dict(
                load_rows(
                    self.instruction_path,
                    HoareStateInstructionRowAdapter,
                )
            )
        except FileNotFoundError:
            self.hash_to_inst = {}

        self.hash_to_state: dict[str, HoareState] = {}

        # update the initial hoare_state_instruction with seed instructions
        for task in self.seed_tasks:
            seed_hoare_state = HoareState(
                start_state=None,
                end_state=self._state_at(task.states, len(task.states) - 1),
                complexity=len(task.states),
            )
            seed_hoare_state_key = seed_hoare_state.to_key()
            self.hash_to_state[seed_hoare_state_key] = seed_hoare_state
            self.hash_to_inst[seed_hoare_state_key] = task.instruction

    def _to_script(self, state_atom: StateAtom) -> str:
        param = "()" if state_atom.param is None else f'("{state_atom.param}")'
        property = "?.".join(f'["{x}"]' for x in state_atom.property)

        if state_atom.return_type == "list":
            return f"""
(() => {{
    const objs = window.{state_atom.f}{param};
    if (objs === undefined) return "";

    const obj = objs.find(el => el?.{property}  === "{state_atom.value}");
    if (obj === undefined) return "";

    return obj?.{property} ?? ""
}})();
"""
        if state_atom.return_type == "obj":
            return f"""
(() => {{
    const obj = window.{state_atom.f}{param};
    if (obj === undefined) return "";

    return obj?.{property} ?? ""
}})();
"""
        raise ValueError(f"Unsupported return type: {state_atom.return_type}")

    def _to_rules(self, state: State) -> list[dict[str, Any]]:
        return [
            {
                "mode": "console",
                "script": self._to_script(state_atom),
                "value": state_atom.value,
                "match": state_atom.match,
                "normalize_space": state_atom.normalize_space,
                "case_sensitive": state_atom.case_sensitive,
            }
            for state_atom in state
        ]

    def _to_setup(self, state: State) -> str:
        by_address: dict[str, dict] = defaultdict(
            lambda: {
                "cell": {},
                "style": {},
            }
        )

        for atom in state:
            if atom.f != "getCellMeta":
                continue

            address = atom.param
            prop = list(atom.property)

            if not prop:
                continue

            root = prop[0]
            path = prop[1:]

            if root not in ("cell", "style"):
                continue

            if not path:
                by_address[address][root] = atom.value
            else:
                set_nested(by_address[address][root], path, atom.value)

        return f"""
(() => {{
    window.applyCellMeta({
            json.dumps(
                [{"address": address, **meta} for address, meta in by_address.items()],
                ensure_ascii=False,
            )
        });
}})();
""".strip()

    def run(self) -> None:
        surfgym_tasks: dict[str, dict[str, Any]] = {}

        for seed in self.seed_tasks:
            state_pair_gen = self._hoare_state_generator(seed.states)

            for hoare, start, end in state_pair_gen:
                hash = hoare.to_key()
                self.hash_to_state[hash] = hoare

                if hash not in self.hash_to_inst:
                    instruction = self.instruction_generator.generate(seed, hoare)
                    self.hash_to_inst[hash] = instruction

                if hash not in surfgym_tasks:
                    surfgym_tasks[hash] = {
                        "task_id": f"{seed.task_id}_{start}_{end}",
                        "instruction": self.hash_to_inst[hash],
                        "website": seed.website,
                        "evaluation": {"rules": self._to_rules(hoare.end_state)},
                        "complexity": hoare.complexity,
                    }

                if hoare.start_state is not None:
                    surfgym_tasks[hash]["setup"] = {
                        "mode": "console",
                        "script": self._to_setup(hoare.start_state),
                    }

        self._dump(list(surfgym_tasks.values()))

    def _state_at(self, states: list[State], idx: int) -> State:
        if self.state_scope == "DELTA":
            return states[idx]

        by_key: dict[Any, StateAtom] = {}
        for state in states[: idx + 1]:
            for atom in state:
                by_key[(atom.f, atom.param, tuple(atom.property))] = atom

        return list(by_key.values())

    def _hoare_state_generator(self, states: list[State]) -> Iterator[tuple[HoareState, int, int]]:
        for end_idx in range(len(states)):
            end_state = self._state_at(states, end_idx)

            if self.granularity == "COARSE":
                yield (
                    HoareState(start_state=None, end_state=end_state, complexity=end_idx + 1),
                    0,
                    end_idx + 1,
                )

            elif self.granularity == "FINE":
                for start_idx in range(-1, end_idx):
                    start_state = None if start_idx == -1 else self._state_at(states, start_idx)

                    yield (
                        HoareState(
                            start_state=start_state,
                            end_state=end_state,
                            complexity=end_idx - start_idx,
                        ),
                        start_idx + 1,
                        end_idx + 1,
                    )

    def _dump(self, surfgym_tasks: list[dict[str, Any]]) -> None:
        (self.output_dir / "augmented.jsonc").write_text(
            json.dumps(surfgym_tasks, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        state_instruction_payload: dict[str, str] = dict(
            sorted(self.hash_to_inst.items(), key=lambda item: item[0])
        )

        self.instruction_path.write_text(
            json.dumps(state_instruction_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        (self.output_dir / "summary.txt").write_text(
            "\n".join(
                [
                    f"seed task count: {len(self.seed_tasks)}",
                    f"generated task count: {len(surfgym_tasks)}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        readable_lines: list[str] = []
        for hash, instruction in sorted(
            self.hash_to_inst.items(),
            key=lambda item: item[0],
        ):
            hoare = self.hash_to_state.get(hash)
            if hoare is None:
                continue

            readable_lines.append("=" * 80)
            readable_lines.append(f"HASH : {hash}")
            readable_lines.append(f"COMPLEXITY : {hoare.complexity}")
            readable_lines.append(f"INSTRUCTION : {instruction}")
            readable_lines.append("=" * 80)
            readable_lines.append("")
            readable_lines.append(
                dumps_state_compact(
                    None
                    if hoare.start_state is None
                    else [atom.model_dump(mode="json") for atom in hoare.start_state],
                )
            )
            readable_lines.append("")
            readable_lines.append("⬇")
            readable_lines.append("")
            readable_lines.append(
                dumps_state_compact([atom.model_dump(mode="json") for atom in hoare.end_state])
            )

        (self.output_dir / "instruction.txt").write_text(
            "\n".join(readable_lines) + "\n",
            encoding="utf-8",
        )


##################################################
#                Helper functions                #
##################################################


def dumps_state_compact(value, indent: int = 8) -> str:
    if value is None:
        return "null"

    pad = " " * indent

    lines = ["["]
    for i, atom in enumerate(value):
        dumped = json.dumps(
            atom,
            ensure_ascii=False,
            separators=(", ", ": "),
        )
        comma = "," if i < len(value) - 1 else ""
        lines.append(f"{pad}{dumped}{comma}")
    lines.append(" " * (indent - 2) + "]")

    return "\n".join(lines)


def load_rows(
    path: Path,
    validator: TypeAdapter[T],
) -> T:
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    if suffix not in {".json", ".jsonl", ".ndjson", ".jsonc"}:
        raise ValueError(f"Unsupported task file type: {path.suffix}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return validator.validate_python([])

    if suffix in {".jsonl", ".ndjson"}:
        payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif suffix == ".jsonc":
        payload = cast(Any, json5.loads(text))
    else:
        payload = json.loads(text)

    return validator.validate_python(payload)


def set_nested(target: dict, path: list[str], value):
    cur = target
    for key in path[:-1]:
        cur = cur.setdefault(key, {})
    cur[path[-1]] = value
