from pathlib import Path

from pydantic import BaseModel, ConfigDict


class FrozneBaseModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class Summary(FrozneBaseModel):
    total: int
    reward_sum: float
    task_source: str
    elapsed_seconds: float


class TaskMeta(FrozneBaseModel):
    snapshot_dir: Path
    reward: float


class Manifest(FrozneBaseModel):
    summary: Summary
    tasks: dict[str, TaskMeta]
