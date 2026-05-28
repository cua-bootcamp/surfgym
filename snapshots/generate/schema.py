from pathlib import Path

from pydantic import BaseModel, ConfigDict


class FrozneBaseModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class Summary(FrozneBaseModel):
    total: int
    succeeded: int
    failed: int
    reward_sum: float
    task_source: str
    elapsed_seconds: float


class TaskMeta(FrozneBaseModel):
    snapshot_dir: Path
    reward: float


class TaskFailure(FrozneBaseModel):
    snapshot_dir: Path
    error_type: str
    error_message: str
    traceback: str


class Manifest(FrozneBaseModel):
    summary: Summary
    tasks: dict[str, TaskMeta]
    failures: dict[str, TaskFailure]
