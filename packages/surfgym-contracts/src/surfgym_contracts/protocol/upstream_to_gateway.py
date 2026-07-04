from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict

from surfgym_contracts.task import Observation


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MasterAllocateResponse(_FrozenBaseModel):
    context_id: str
    instance_host: str
    instance_port: int


class InstanceAllocateResponse(_FrozenBaseModel):
    pass


class ScreenshotResponse(_FrozenBaseModel):
    screenshot_b64: str
    media_type: str
    x: float
    y: float


class ObservationResponse(_FrozenBaseModel):
    observation: list[Observation]


class IdleResponse(_FrozenBaseModel):
    idle: bool


class ExecuteResponse(_FrozenBaseModel):
    pass


class ReleaseResponse(_FrozenBaseModel):
    pass


InstanceErrorType: TypeAlias = Literal[
    "INSTANCE_UNEXPECTED",
    "INSTANCE_NOT_IDLE",
    "INSTNACE_IDLE",
    "INVALID_INSTANCE_ID",
    "CREATE_FAILED",
    "INSTANCE_IDLE",
    "INVALID_COMMAND",
]
UpstreamErrorType: TypeAlias = (
    Literal["OUT_OF_INSTANCE", "UNEXPECTED", "INSTANCE_REQUEST_FAILED"] | InstanceErrorType
)


class ErrorResponse(_FrozenBaseModel):
    message: str
    retryable: bool = False
