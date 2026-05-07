from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.components.task import Website


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GetInstanceRequest(_FrozenBaseModel):
    websites: list[Website] = Field(min_length=1)
