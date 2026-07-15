import sqlite3
import threading
from pathlib import Path

from surfgym_contracts.task import Task


class TaskStore:
    """SQLite-backed task lookup store."""

    def __init__(self, database_path: str | Path) -> None:
        path = Path(database_path)
        if not (path.exists() and path.is_file()):
            raise FileNotFoundError(path)

        self._connection = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro", uri=True, check_same_thread=False
        )
        self._lock = threading.Lock()

        self._validate_schema()

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            row = self._connection.execute(
                """
    SELECT payload
    FROM tasks
    WHERE task_id = ?
    """.strip(),
                (str(task_id),),
            ).fetchone()

        if row is None:
            return None

        return Task.model_validate_json(row[0])

    def task_ids(self) -> list[str]:
        with self._lock:
            rows = self._connection.execute(
                """
        SELECT task_id
        FROM tasks
        ORDER BY rowid
        """.strip()
            ).fetchall()

        return [row[0] for row in rows]

    def _validate_schema(self) -> None:
        rows = self._connection.execute("PRAGMA table_info(tasks)").fetchall()
        columns = {row[1] for row in rows}
        required_columns = {"task_id", "payload"}
        missing_columns = required_columns - columns

        if missing_columns:
            names = ", ".join(sorted(missing_columns))
            raise ValueError(f"Invalid task database schema; missing columns: {names}")

    def close(self):
        self._connection.close()
