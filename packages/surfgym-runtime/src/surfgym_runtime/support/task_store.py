import sqlite3
from contextlib import closing
from pathlib import Path

from surfgym_contracts.task import Task


class TaskStore:
    """SQLite-backed task lookup store."""

    def __init__(self, database_path: str | Path) -> None:
        path = Path(database_path)

        if not path.exists():
            raise FileNotFoundError(path)

        if not path.is_file():
            raise ValueError(f"Task database path is not a file: {path}")

        self._database_uri = f"{path.resolve().as_uri()}?mode=ro"
        self._validate_schema()

    def get(self, task_id: str | int) -> Task | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
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
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
    SELECT task_id
    FROM tasks
    ORDER BY rowid
    """.strip()
            ).fetchall()

        return [row[0] for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(
            self._database_uri,
            uri=True,
        )

    def _validate_schema(self) -> None:
        with closing(self._connect()) as connection:
            rows = connection.execute("PRAGMA table_info(tasks)").fetchall()

        columns = {row[1] for row in rows}
        required_columns = {"task_id", "payload"}
        missing_columns = required_columns - columns

        if missing_columns:
            names = ", ".join(sorted(missing_columns))
            raise ValueError(f"Invalid task database schema; missing columns: {names}")
