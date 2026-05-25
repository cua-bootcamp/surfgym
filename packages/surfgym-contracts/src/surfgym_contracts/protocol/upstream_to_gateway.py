from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict

from surfgym_contracts.task import Observation


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AllocateResponse(_FrozenBaseModel):
    instance_id: str
    instance_host: str
    instance_port: int


class GetInstanceResponse(_FrozenBaseModel):
    instance_id: str


class ScreenshotResponse(_FrozenBaseModel):
    snapshot_b64: str
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


UpstreamErrorType: TypeAlias = Literal["OUT_OF_INSTANCE", "UNEXPECTED", "INSTANCE_REQUEST_FAILED"]


class ErrorResponse(_FrozenBaseModel):
    error_type: UpstreamErrorType
    message: str
    retryable: bool = False


# class InstanceServerErrorType(str, Enum):
#     INSTANCE_NOT_IDLE = "INSTANCE_NOT_IDLE"
#     INSTANCE_IDLE = "INSTANCE_IDLE"
#     INVALID_COMMAND = "INVALID_COMMAND"
#     INVALID_INSTANCE_ID = "INVALID_INSTANCE_ID"
#     CREATE_FAILED = "CREATE_FAILED"


# class InteractiveTreeResponse(_FrozenBaseModel):
#     mouse_position: MousePosition
#     regions: list[InteractiveRegion]
# class InteractiveRegion(_FrozenBaseModel):
#     role: str
#     visible_text: str
#     bbox: tuple[float, float, float, float]  # [left, top, width, height]
# interactive_region_list_adapter = TypeAdapter(list[InteractiveRegion])
# class MousePosition(_FrozenBaseModel):
#     x: int
#     y: int
