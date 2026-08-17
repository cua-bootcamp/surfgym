import json
import shutil
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Tuple, TypeVar

from pydantic import TypeAdapter
from surfgym_contracts.task import Task

from surfgym_task.hoare import HoareState
from surfgym_task.instruction_generator import InstructionGenerator
from surfgym_task.seed import (
    CriteriaSeedTask,
    Domain,
    InfeasibleSeedTask,
    LLMJudgeSeedTask,
    RawInfeasibleSeedTask,
    RawLLMJudgeSeedTask,
    RawSeedTask,
    SeedTask,
    State,
)

T = TypeVar("T")

COMMIT_EVERY = 30


@dataclass
class Summary:
    seed_count: int = 0
    task_count: int = 0


class JsonIO:
    @staticmethod
    def read(path: Path) -> object:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)

    @staticmethod
    def write(path: Path, value: object) -> None:
        payload = TypeAdapter(type(value)).dump_python(value, mode="json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as stream:
            json.dump(
                payload,
                stream,
                ensure_ascii=False,
                indent=2,
            )
            stream.write("\n")


class SQLiteIO:
    def __init__(self, path: Path):
        self.path = path
        self.connection: sqlite3.Connection | None = None

        self.pending: int = 0
        self.commit_every: int = COMMIT_EVERY

    def __enter__(self) -> "SQLiteIO":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.connection is None:
            return

        try:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()
            self.connection = None

    def execute(
        self,
        sql: str,
        parameters: tuple[object, ...] = (),
    ) -> sqlite3.Cursor:
        self._flush_pending()
        return self._require_connection().execute(sql, parameters)

    def commit(self):
        self._require_connection().commit()

    def _flush_pending(self):
        self.pending += 1
        if self.pending >= self.commit_every:
            self.pending = 0
            self.commit()

    def _require_connection(self) -> sqlite3.Connection:
        if self.connection is None:
            raise RuntimeError("SQLiteIO is not open.")
        return self.connection


class SeedReader:
    """
    Read a RawSeedTask and transform it into a SeedTask.
    """

    def __init__(self, seeds_dir: Path):
        self.seeds_dir = seeds_dir

    def get_seed(self) -> Iterator[Tuple[SeedTask, str]]:
        for seed_path in self.seeds_dir.glob("*.json"):
            raw_seed = TypeAdapter[RawSeedTask](RawSeedTask).validate_python(JsonIO.read(seed_path))
            yield (self._adhoc_transformation(raw_seed), seed_path.stem)

    def _adhoc_transformation(self, raw_seed: RawSeedTask) -> SeedTask:
        domain = (
            raw_seed.domain
            if raw_seed.domain is not None
            else TypeAdapter[Domain](Domain).validate_python(self.seeds_dir.parent.name)
        )

        if isinstance(raw_seed, RawLLMJudgeSeedTask):
            return LLMJudgeSeedTask(
                domain=domain,
                instruction=raw_seed.instruction,
                evaluation=raw_seed.evaluation,
                website=raw_seed.website.to_url(),
            )

        if isinstance(raw_seed, RawInfeasibleSeedTask):
            return InfeasibleSeedTask(
                domain=domain,
                instruction=raw_seed.instruction,
                evaluation=raw_seed.evaluation,
                website=raw_seed.website.to_url(),
            )

        match domain:
            case "spreadsheet" | "word":
                empty_start = False if raw_seed.empty_start is None else raw_seed.empty_start
            case "impress" | "gimp" | "vlc":
                empty_start = True if raw_seed.empty_start is None else raw_seed.empty_start

        states = list(raw_seed.states)
        if empty_start:
            states.insert(0, State(atoms=[]))

        return CriteriaSeedTask(
            domain=domain,
            instruction=raw_seed.instruction,
            states=states,
            accumulation=raw_seed.accumulation or "CUMULATIVE",
            website=raw_seed.website.to_url(),
        )


class DetailWriter:
    def __init__(self, out_directory: Path):
        self._detail_directory = out_directory / "detail"
        if self._detail_directory.exists():
            shutil.rmtree(self._detail_directory)

    def write_task(self, task: Task) -> None:
        parts = task.task_id.rsplit("_", 2)

        if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            seed_name, start_idx, end_idx = parts
            path = self._detail_directory / seed_name / f"{start_idx}_{end_idx}.json"
        else:
            path = self._detail_directory / f"{task.task_id}.json"

        JsonIO.write(path, task)

    def write_summary(self, summary: Summary):
        path = self._detail_directory / "summary.json"
        JsonIO.write(path, summary)


class InstructionWriter:
    def __init__(
        self,
        database_path: Path,
    ):
        self.database = SQLiteIO(database_path)
        self.insturction_generator = InstructionGenerator()

    def __enter__(self) -> "InstructionWriter":
        self.database.__enter__()
        self.database.execute(
            """
CREATE TABLE IF NOT EXISTS instructions (
    task_hash TEXT PRIMARY KEY,
    instruction TEXT NOT NULL
)
""".strip()
        )
        self.database.commit()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.database.__exit__(exc_type, exc_value, traceback)

    def get(
        self,
        task_hash: str,
        seed: CriteriaSeedTask,
        hoare_state: HoareState,
    ) -> str:
        instruction = self._get_instruction(task_hash)
        if instruction is not None:
            return instruction

        instruction = self.insturction_generator.generate(seed, hoare_state)
        self._upsert_instruction(task_hash, instruction)
        return instruction

    def _get_instruction(self, task_hash: str) -> str | None:
        row = self.database.execute(
            """
SELECT instruction
FROM instructions
WHERE task_hash = ?
        """.strip(),
            (task_hash,),
        ).fetchone()

        return None if row is None else row[0]

    def _upsert_instruction(
        self,
        task_hash: str,
        instruction: str,
    ):
        self.database.execute(
            """
INSERT INTO instructions (task_hash, instruction)
VALUES (?, ?)
ON CONFLICT(task_hash)
DO UPDATE SET instruction = excluded.instruction
            """.strip(),
            (task_hash, instruction),
        )


class TaskWriter:
    def __init__(
        self,
        database_path: Path,
    ):
        self.database = SQLiteIO(database_path)
        self.pending: int = 0
        self.commit_every: int = COMMIT_EVERY

    def __enter__(self) -> "TaskWriter":
        self.database.__enter__()

        self.database.execute("DROP TABLE IF EXISTS tasks")
        self.database.execute(
            """
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
)
""".strip()
        )

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.database.__exit__(exc_type, exc_value, traceback)

    def write(self, task: Task) -> None:
        self.database.execute(
            """
INSERT INTO tasks (task_id, payload)
VALUES (?, ?)
""".strip(),
            (
                task.task_id,
                task.model_dump_json(),
            ),
        )
