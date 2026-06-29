import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, TypedDict, TypeVar

from pydantic import TypeAdapter
from surfgym_contracts.task import Task

from surfgym_task.hoare import HoareState
from surfgym_task.instruction_generator import (
    InstructionGenerator,
    InstructionPayload,
    build_instruction_payload,
)
from surfgym_task.seed import Accumulation, RawSeedTask, SeedTask


@dataclass(frozen=True)
class DataPaths:
    root_dir: Path
    seeds_dir: Path
    out_dir: Path
    instruction: Path


def resolve_datapaths(target_dir: Path) -> DataPaths:
    seeds_dir = target_dir / "seeds"
    out_dir = target_dir / "out"
    instruction = target_dir / "instruction.jsonl"

    if not target_dir.exists() or not target_dir.is_dir():
        raise FileNotFoundError(f"Directory not found: {target_dir}")
    if not seeds_dir.exists() or not seeds_dir.is_dir():
        raise FileNotFoundError(f"Seeds directory not found: {seeds_dir}")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    instruction.touch(exist_ok=True)

    return DataPaths(
        root_dir=target_dir,
        seeds_dir=seeds_dir,
        instruction=instruction,
        out_dir=out_dir,
    )


class DefaultTaskValues(TypedDict):
    empty_start: bool
    accumulation: Accumulation
    website: str


DEFAULT_TASK_VALUES: dict[str, DefaultTaskValues] = {
    "spreadsheet": {
        "empty_start": False,
        "accumulation": "CUMULATIVE",
        "website": "http://localhost:3000/spreadsheet",
    },
    "word": {
        "empty_start": False,
        "accumulation": "CUMULATIVE",
        "website": "http://localhost:3000/word",
    },
    "impress": {
        "empty_start": True,
        "accumulation": "CUMULATIVE",
        "website": "http://localhost:53001/impress",
    },
}


RawSeedTaskAdapter: TypeAdapter[RawSeedTask] = TypeAdapter(RawSeedTask)


def iterate_seed(seeds_dir: Path) -> Iterator[tuple[SeedTask, str]]:
    for path in sorted(seeds_dir.glob("*.json")):
        domain = seeds_dir.parent.name
        raw_seed = load_rows(path, RawSeedTaskAdapter)

        defaults = DEFAULT_TASK_VALUES.get(domain)
        if defaults is None:
            raise ValueError(f"No default values for domain: {domain}")

        empty_start = (
            raw_seed.empty_start if raw_seed.empty_start is not None else defaults["empty_start"]
        )

        if empty_start:
            raw_seed.states.insert(0, [])

        yield (
            SeedTask(
                domain=domain,
                instruction=raw_seed.instruction,
                states=raw_seed.states,
                accumulation=raw_seed.accumulation
                if raw_seed.accumulation
                else defaults["accumulation"],
                website=raw_seed.website if raw_seed.website else defaults["website"],
            ),
            f"{domain}_{path.stem}",
        )


@dataclass
class RunStats:
    seed_count: int = 0
    task_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "seed_count": self.seed_count,
            "task_count": self.task_count,
        }


class JsonWriter:
    def __init__(self, path: Path, flush_every: int = 10):
        self.path = path
        self.flush_every = flush_every
        self.count = 0

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fp = self.path.open("w", encoding="utf-8")

    def __enter__(self) -> "JsonWriter":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def write(self, row: Mapping[str, Any]) -> None:
        self.fp.write(
            json.dumps(
                row,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )

        self.count += 1
        if self.count % self.flush_every == 0:
            self.flush()

    def flush(self) -> None:
        self.fp.flush()

    def close(self) -> None:
        self.flush()
        self.fp.close()


class TaskWriter:
    def __init__(self, seed_dir: Path):
        self.seed_dir = seed_dir

    def __enter__(self) -> "TaskWriter":
        self.seed_dir.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def _task_dir(self, f: int, t: int) -> Path:
        task_dir = self.seed_dir / f"{f}_{t}"
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def _write_json(self, f: int, t: int, filename: str, value: object) -> None:
        (self._task_dir(f, t) / filename).write_text(
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_task(self, f: int, t: int, task: Task) -> None:
        self._write_json(f, t, "task.json", task.model_dump(mode="json"))

    def write_payload(self, f: int, t: int, payload: InstructionPayload) -> None:
        self._write_json(f, t, "payload.json", payload)


class AugmentationWriter:
    def __init__(self, out_dir: Path, flush_every: int = 10):
        self.out_dir = out_dir
        self.detail_dir = out_dir / "detail"
        self.flush_every = flush_every

    def __enter__(self) -> "AugmentationWriter":
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.detail_dir.mkdir(parents=True, exist_ok=True)
        self.augmented = JsonWriter(self.out_dir / "augmented.jsonl", self.flush_every)
        return self

    def __exit__(self, *args: object) -> None:
        self.augmented.close()

    def open_seed(self, seed_id: str) -> TaskWriter:
        return TaskWriter(self.detail_dir / seed_id)

    def write_task(self, task: Task) -> None:
        self.augmented.write(task.model_dump(mode="json"))

    def write_summary(self, stats: RunStats) -> None:
        summary_path = self.out_dir / "summary.json"
        summary_path.write_text(
            json.dumps(
                stats.to_dict(),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


class InstructionLoader:
    def __init__(self, path: Path, flush_every: int = 10):
        self.path = path
        self.count = 0
        self.flush_every = flush_every
        self.instruction_generator = InstructionGenerator()
        rows = load_rows(
            path,
            TypeAdapter(list[dict[str, str]]),
            default=[],
        )

        self.instructions: dict[str, str] = {}
        for row in rows:
            task_hash = row.get("hash")
            instruction = row.get("instruction")

            if task_hash is None or instruction is None:
                raise ValueError(f"Invalid instruction row in {path}: {row}")

            self.instructions[task_hash] = instruction

    def get(
        self,
        task_hash: str,
        seed: SeedTask,
        hoare_state: HoareState,
    ) -> tuple[str, InstructionPayload]:
        payload = build_instruction_payload(seed, hoare_state)

        instruction = self.instructions.get(task_hash)
        if instruction is not None:
            return instruction, payload

        instruction = self.instruction_generator.generate(payload)
        self.instructions[task_hash] = instruction

        self.count += 1
        if self.count % self.flush_every == 0:
            self.flush()

        return instruction, payload

    def flush(self) -> None:
        with JsonWriter(self.path, self.flush_every) as writer:
            for task_hash, instruction in sorted(self.instructions.items()):
                writer.write(
                    {
                        "hash": task_hash,
                        "instruction": instruction,
                    }
                )


T = TypeVar("T")


def load_rows(path: Path, validator: TypeAdapter[T], default: T | None = None) -> T:
    if not path.exists():
        if default is None:
            raise FileNotFoundError(path)
        return validator.validate_python(default)

    suffix = path.suffix.lower()
    if suffix not in {".json", ".jsonl", ".ndjson"}:
        raise ValueError(f"Unsupported task file type: {path.suffix}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        if default is None:
            raise ValueError(f"Empty task file: {path}")
        return validator.validate_python(default)

    payload = (
        [json.loads(line) for line in text.splitlines() if line.strip()]
        if suffix in {".jsonl", ".ndjson"}
        else json.loads(text)
    )
    return validator.validate_python(payload)
