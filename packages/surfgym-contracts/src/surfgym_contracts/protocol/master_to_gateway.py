from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MasterServerErrorType(str, Enum):
    NO_INSTANCES_AVAILABLE = "NO_INSTANCES_AVAILABLE"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"


class GetInstanceResponse(_FrozenBaseModel):
    instance_id: str
    instance_host: str
    instance_port: int


class ErrorResponse(_FrozenBaseModel):
    error_type: MasterServerErrorType
    message: str
