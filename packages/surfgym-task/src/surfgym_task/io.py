import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Tuple, TypeVar, get_args

from pydantic import TypeAdapter
from surfgym_contracts.task import Task

from surfgym_task.hoare import HoareState
from surfgym_task.instruction_generator import InstructionGenerator
from surfgym_task.seed import Domain, RawSeedTask, SeedTask

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
    def validate(path: Path, schema: type[T]) -> T:
        payload = JsonIO.read(path)
        return TypeAdapter(schema).validate_python(payload)

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
            raw_seed = JsonIO.validate(seed_path, RawSeedTask)
            yield (self._adhoc_transformation(raw_seed), seed_path.stem)

    def _adhoc_transformation(self, raw_seed: RawSeedTask) -> SeedTask:
        domain = raw_seed.domain or self.seeds_dir.parent.name
        if domain not in get_args(Domain.__value__):
            raise ValueError(f"Unsupported domain: {domain}")

        if domain == "spreadsheet" or domain == "word":
            empty_start = raw_seed.empty_start or False
            if empty_start:
                raw_seed.states.insert(0, [])

            return SeedTask(
                domain=domain,
                instruction=raw_seed.instruction,
                states=raw_seed.states,
                accumulation=raw_seed.accumulation or "CUMULATIVE",
                website=raw_seed.website or f"http://localhost:3000/{domain}",
            )

        if domain == "impress":
            if raw_seed.setup_file is None:
                raise ValueError("Need a setup file")

            empty_start = raw_seed.empty_start or True
            if empty_start:
                raw_seed.states.insert(0, [])

            return SeedTask(
                domain=domain,
                instruction=raw_seed.instruction,
                states=raw_seed.states,
                accumulation=raw_seed.accumulation or "CUMULATIVE",
                website=raw_seed.website
                or f"http://localhost:53001/{domain}?setup_file={raw_seed.setup_file}",
            )

        else:
            raise ValueError("Unimplemented")


class DetailWriter:
    def __init__(self, out_directory: Path):
        self._detail_directory = out_directory / "detail"

    def write_task(self, task: Task):
        seed_name, idx1, idx2 = task.task_id.rsplit("_", 2)
        path = self._detail_directory / seed_name / f"{idx1}_{idx2}.json"
        JsonIO.write(path, task)

    def write_summary(self, summary: Summary):
        path = self._detail_directory / "summary.json"
        JsonIO.write(path, summary)


class InstructionLoader:
    def __init__(
        self,
        database_path: Path,
    ):
        self.database = SQLiteIO(database_path)
        self.insturction_generator = InstructionGenerator()

    def __enter__(self) -> "InstructionLoader":
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
        seed: SeedTask,
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
