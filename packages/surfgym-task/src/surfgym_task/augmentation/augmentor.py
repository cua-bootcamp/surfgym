import json
from pathlib import Path
from typing import Any, Iterator, Optional, TypeVar, cast

import json5
from pydantic import TypeAdapter
from surfgym_contracts import Action, ConsoleRule, Evaluation, Task

from surfgym_task.augmentation.instruction_generator import InstructionGenerator
from surfgym_task.augmentation.schema import (
    Accumulation,
    Granularity,
    HoareState,
    HoareStateInstructionRowAdapter,
    SeedTask,
    State,
    StateAtom,
    TaskRowsAdapter,
)

T = TypeVar("T")


class Augmentor:
    def __init__(
        self, seed_dir: Path, granularity: Granularity, accumulation: Accumulation
    ) -> None:
        self.granularity: Granularity = granularity
        self.instruction_generator = InstructionGenerator()

        self.seed_path = seed_dir / "seed.jsonc"
        self.instruction_path = seed_dir / "instruction.jsonc"
        self.output_dir = seed_dir / "out"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.seeds: list[SeedTask] = load_rows(self.seed_path, TaskRowsAdapter)
        self.hash_to_inst = load_rows(self.instruction_path, HoareStateInstructionRowAdapter, {})
        self.hash_to_state: dict[str, HoareState] = {}

        self.hoare_creator = HoareState.creator(accumulation)

        # update the initial hoare_state_instruction with seed instructions
        for seed in self.seeds:
            seed_hoare = self.hoare_creator(seed.states, len(seed.states) - 1)
            seed_hoare_key = seed_hoare.to_key()
            self.hash_to_state[seed_hoare_key] = seed_hoare
            self.hash_to_inst[seed_hoare_key] = seed.instruction

    def run(self) -> None:
        surfgym_tasks: list[Task] = []

        for seed in self.seeds:
            state_pair_gen = self._hoare_state_generator(seed.states)

            for hoare, start, end in state_pair_gen:
                hash = hoare.to_key()
                self.hash_to_state[hash] = hoare

                if hash not in self.hash_to_inst:
                    instruction = self.instruction_generator.generate(seed, hoare)
                    self.hash_to_inst[hash] = instruction

                surfgym_tasks.append(
                    Task(
                        task_id=f"{seed.task_id}_{start}_{end}",
                        instruction=self.hash_to_inst[hash],
                        website=seed.website,
                        complexity=hoare.complexity,
                        evaluation=Evaluation(rules=self._state_to_rules(hoare.end_state)),
                        setup=(
                            None
                            if hoare.start_state is None
                            else self._state_to_actions(hoare.start_state)
                        ),
                        transition=self._state_to_actions(hoare.end_state),
                    )
                )

        self._dump(surfgym_tasks)

    def _state_to_rules(self, state: State) -> list[ConsoleRule]:
        return [
            ConsoleRule(
                script=self._atom_to_script(atom),
                value=atom.value,
                match=atom.match,
                normalize_space=atom.normalize_space,
                case_sensitive=atom.case_sensitive,
            )
            for atom in state
        ]

    def _atom_to_script(self, state_atom: StateAtom) -> str:
        param = "()" if state_atom.param is None else f'("{state_atom.param}")'
        property = "?.".join(f'["{x}"]' for x in state_atom.property)

        if state_atom.return_type == "list":
            return f"""
(() => {{
    const objs = window.{state_atom.evalf}{param};
    const obj = objs.find(el => el?.{property}  === "{state_atom.value}");
    return obj.{property}
}})();
"""
        if state_atom.return_type == "obj":
            return f"""
(() => {{
    const obj = window.{state_atom.evalf}{param};
    return obj.{property}
}})();
"""
        raise ValueError(f"Unsupported return type: {state_atom.return_type}")

    def _state_to_actions(self, state: State) -> list[Action]:
        return [Action(mode="console", script=self._atom_to_action_script(atom)) for atom in state]

    def _atom_to_action_script(self, atom: StateAtom) -> str:
        payload = {
            "param": atom.param,
            "property": atom.property,
            "value": atom.value,
        }

        return f"""
(() => {{
    const atom = {json.dumps(payload, ensure_ascii=False)};
    const applyf = {json.dumps(atom.applyf, ensure_ascii=False)};

    const isRecord = (value) =>
        value !== null && typeof value === "object" && !Array.isArray(value);

    const setNested = (target, path, value) => {{
        if (path.length === 0) return value;

        let cur = target;
        for (const key of path.slice(0, -1)) {{
            if (!isRecord(cur[key])) {{
                cur[key] = {{}};
            }}
            cur = cur[key];
        }}

        cur[path[path.length - 1]] = value;
        return target;
    }};

    const entry = {{}};
    if (atom.param !== null && atom.param !== undefined) {{
        entry.address = atom.param;
    }}

    setNested(entry, atom.property ?? [], atom.value);

    const apply = window[applyf];
    if (typeof apply !== "function") {{
        throw new Error(`Missing setup apply function: ${{applyf}}`);
    }}

    apply([entry]);
}})();
""".strip()

    def _hoare_state_generator(self, states: list[State]) -> Iterator[tuple[HoareState, int, int]]:
        for end_idx in range(len(states)):
            if self.granularity == "COARSE":
                yield (self.hoare_creator(states, end_idx), 0, end_idx + 1)

            elif self.granularity == "FINE":
                for start_idx in range(-1, end_idx):
                    yield (
                        self.hoare_creator(states, end_idx, start_idx),
                        start_idx + 1,
                        end_idx + 1,
                    )

    def _dump(self, surfgym_tasks: list[Task]) -> None:
        (self.output_dir / "augmented.jsonc").write_text(
            json.dumps(
                [task.model_dump(mode="json", exclude_none=True) for task in surfgym_tasks],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
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
                    f"seed task count: {len(self.seeds)}",
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

            separator = "=" * 80
            start_state = (
                None
                if hoare.start_state is None
                else [atom.model_dump(mode="json") for atom in hoare.start_state]
            )
            end_state = [atom.model_dump(mode="json") for atom in hoare.end_state]

            readable_lines.extend(
                f"""\
            {separator}
            HASH : {hash}
            COMPLEXITY : {hoare.complexity}
            INSTRUCTION : {instruction}
            {separator}

            {dumps_state_compact(start_state)}

            ⬇

            {dumps_state_compact(end_state)}
            """.splitlines()
            )

        (self.output_dir / "instruction.txt").write_text(
            "\n".join(readable_lines) + "\n",
            encoding="utf-8",
        )


##################################################
#                Helper functions                #
##################################################


def dumps_state_compact(value: Optional[list[dict[Any, str]]], indent: int = 8) -> str:
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


def load_rows(path: Path, validator: TypeAdapter[T], init: Optional[T] = None) -> T:
    if not path.exists():
        if init:
            return init
        else:
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
