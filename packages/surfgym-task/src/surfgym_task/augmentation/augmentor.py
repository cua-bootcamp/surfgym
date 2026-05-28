import json
from pathlib import Path
from typing import Any, Iterator, Optional, TextIO, TypeVar, cast

import json5
from pydantic import TypeAdapter
from surfgym_contracts import Action, ConsoleRule, Evaluation, Task, Website

from surfgym_task.augmentation.instruction_generator import InstructionGenerator
from surfgym_task.augmentation.schema import (
    Accumulation,
    Granularity,
    HoareState,
    SeedTask,
    SeedTaskAdapter,
    State,
    StateAtom,
)

T = TypeVar("T")


class Augmentor:
    def __init__(
        self, seed_dir: Path, granularity: Granularity, accumulation: Accumulation, website: str
    ) -> None:
        if not seed_dir.exists():
            raise FileNotFoundError(f"Seed directory not found: {seed_dir}")
        if not seed_dir.is_dir():
            raise NotADirectoryError(seed_dir)

        seeds_dir = seed_dir / "seeds"
        if not seeds_dir.exists():
            raise FileNotFoundError(f"Seeds directory not found: {seeds_dir}")
        if not seeds_dir.is_dir():
            raise NotADirectoryError(seeds_dir)

        self.website = website
        self.granularity: Granularity = granularity
        self.instruction_generator = InstructionGenerator()

        legacy_instruction_path = seed_dir / "instruction.jsonc"
        self.instruction_path = seed_dir / "instruction.jsonl"
        if not self.instruction_path.exists():
            self.instruction_path.touch()

        self.output_dir = seed_dir / "out"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.seeds_with_ids = load_seed_tasks(seeds_dir)
        self.hash_to_inst = load_instruction_rows(self.instruction_path)
        if not self.hash_to_inst and legacy_instruction_path.exists():
            self.hash_to_inst = load_instruction_object(legacy_instruction_path)

        self.hash_to_state: dict[str, HoareState] = {}

        self.hoare_creator = HoareState.creator(accumulation)

        # update the initial hoare_state_instruction with seed instructions
        for seed, _ in self.seeds_with_ids:
            seed_hoare = self.hoare_creator(
                seed.states, len(seed.states) - 1, -1 if seed.empty_start else 0
            )
            seed_hoare_key = seed_hoare.to_key()
            self.hash_to_state[seed_hoare_key] = seed_hoare
            self.hash_to_inst[seed_hoare_key] = seed.instruction

    def run(self) -> None:
        generated_task_count = 0

        with (self.output_dir / "augmented.jsonl").open("w", encoding="utf-8") as fp:
            for seed, id in self.seeds_with_ids:
                state_pair_gen = self._hoare_state_generator(seed.states, seed.empty_start)

                for hoare, start, end in state_pair_gen:
                    hash = hoare.to_key()
                    self.hash_to_state[hash] = hoare

                    if hash not in self.hash_to_inst:
                        instruction = self.instruction_generator.generate(seed, hoare)
                        self.hash_to_inst[hash] = instruction

                    task = Task(
                        hash=hash,
                        task_id=f"{id}_{start}_{end}",
                        instruction=self.hash_to_inst[hash],
                        website=[Website(url=self.website)],
                        complexity=hoare.complexity,
                        evaluation=Evaluation(rules=self._state_to_rules(hoare.end_state)),
                        setup=(
                            None
                            if hoare.start_state is None
                            else self._state_to_actions(hoare.start_state)
                        ),
                        transition=self._state_to_actions(hoare.end_state),
                    )
                    write_task_row(fp, task)
                    generated_task_count += 1

        self._dump(generated_task_count)

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
        property = "".join(f'["{x}"]' for x in state_atom.property)
        expected = json.dumps(state_atom.value, ensure_ascii=False)

        if state_atom.return_type == "list":
            return f"""
(() => {{
    const objs = window[{json.dumps(state_atom.evalf)}]{param};
    const obj = objs.find(el => el?.{property} === {expected});
    return obj{property}
}})();
""".strip()

        if state_atom.return_type == "obj":
            return f"""
(() => {{
    const obj = window[{json.dumps(state_atom.evalf)}]{param};
    return obj{property}
}})();
""".strip()

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

    const apply = window[{json.dumps(atom.applyf)}];
    if (typeof apply !== "function") {{
        throw new Error(`Missing setup apply function: {atom.applyf}`);
    }}

    apply([entry]);
}})();
""".strip()

    def _hoare_state_generator(
        self, states: list[State], empty_start: bool
    ) -> Iterator[tuple[HoareState, int, int]]:
        for end_idx in range(0 if empty_start else 1, len(states)):
            if self.granularity == "COARSE":
                start_idx = -1 if empty_start else 0
                yield (
                    self.hoare_creator(states, end_idx, start_idx),
                    start_idx + 1,
                    end_idx + 1,
                )

            elif self.granularity == "FINE":
                for start_idx in range(-1 if empty_start else 0, end_idx):
                    yield (
                        self.hoare_creator(states, end_idx, start_idx),
                        start_idx + 1,
                        end_idx + 1,
                    )

    def _dump(self, generated_task_count: int) -> None:
        write_instruction_rows(self.instruction_path, self.hash_to_inst)

        (self.output_dir / "summary.txt").write_text(
            "\n".join(
                [
                    f"seed task count: {len(self.seeds_with_ids)}",
                    f"generated task count: {generated_task_count}",
                ]
            )
            + "\n",
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


def load_seed_tasks(seeds_dir: Path) -> list[tuple[SeedTask, str]]:
    if not seeds_dir.exists():
        raise FileNotFoundError(seeds_dir)
    if not seeds_dir.is_dir():
        raise NotADirectoryError(seeds_dir)

    json_paths = sorted(
        path for path in seeds_dir.iterdir() if path.is_file() and path.suffix == ".json"
    )
    if not json_paths:
        raise FileNotFoundError(f"No seed JSON files found in {seeds_dir}")

    domain_name = seeds_dir.parent.name
    return [(load_rows(path, SeedTaskAdapter), f"{domain_name}_{path.stem}") for path in json_paths]


def load_instruction_rows(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    instructions: dict[str, str] = {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return instructions

    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue

        row = json.loads(line)
        if row == {}:
            continue
        if not isinstance(row, dict):
            raise ValueError(f"Invalid instruction row at {path}:{line_no}: expected object")

        hash_value = row.get("hash")  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        instruction = row.get("instruction")  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        if not isinstance(hash_value, str) or not isinstance(instruction, str):
            raise ValueError(
                f"Invalid instruction row at {path}:{line_no}: "
                'expected string "hash" and "instruction" fields'
            )

        instructions[hash_value] = instruction

    return instructions


def load_instruction_object(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}

    payload = cast(Any, json5.loads(text)) if path.suffix == ".jsonc" else json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid instruction cache at {path}: expected object")

    instructions: dict[str, str] = {}
    for hash_value, instruction in payload.items():  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(hash_value, str) or not isinstance(instruction, str):
            raise ValueError(
                f"Invalid instruction cache at {path}: expected string keys and values"
            )
        instructions[hash_value] = instruction

    return instructions


def write_instruction_rows(path: Path, instructions: dict[str, str]) -> None:
    with path.open("w", encoding="utf-8") as fp:
        for hash_value, instruction in sorted(instructions.items(), key=lambda item: item[0]):
            fp.write(
                json.dumps(
                    {"hash": hash_value, "instruction": instruction},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )


def write_task_row(fp: TextIO, task: Task) -> None:
    fp.write(
        json.dumps(
            task.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    )


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
        return validator.validate_python({})

    if suffix in {".jsonl", ".ndjson"}:
        payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif suffix == ".jsonc":
        payload = cast(Any, json5.loads(text))
    else:
        payload = json.loads(text)

    return validator.validate_python(payload)
