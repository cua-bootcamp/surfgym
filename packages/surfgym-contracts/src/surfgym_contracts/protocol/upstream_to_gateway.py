from __future__ import annotations

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


class InsatnceReleaseResponse(_FrozenBaseModel):
    pass


MasterReleaseResponse = InsatnceReleaseResponse


class ScreenshotResponse(_FrozenBaseModel):
    screenshot_b64: str
    media_type: str
    x: float
    y: float


class IdleResponse(_FrozenBaseModel):
    idle: bool


class ObserveResponse(_FrozenBaseModel):
    observation: list[Observation]


class ExecuteResponse(_FrozenBaseModel):
    pass


class ErrorResponse(_FrozenBaseModel):
    message: str
    retryable: bool = False
