from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, TypeAdapter

from surfgym_contracts.task import Observation


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class InstanceServerErrorType(str, Enum):
    INSTANCE_NOT_IDLE = "INSTANCE_NOT_IDLE"
    INSTANCE_IDLE = "INSTANCE_IDLE"
    INVALID_COMMAND = "INVALID_COMMAND"
    INVALID_INSTANCE_ID = "INVALID_INSTANCE_ID"
    CREATE_FAILED = "CREATE_FAILED"


class GetInstanceResponse(_FrozenBaseModel):
    instance_id: str


class ScreenshotResponse(_FrozenBaseModel):
    snapshot_b64: str
    media_type: str
    x: float
    y: float


class ObservationResponse(_FrozenBaseModel):
    observation: list[Observation]


class InteractiveTreeResponse(_FrozenBaseModel):
    mouse_position: MousePosition
    regions: list[InteractiveRegion]


class InteractiveRegion(_FrozenBaseModel):
    role: str
    visible_text: str
    bbox: tuple[float, float, float, float]  # [left, top, width, height]


interactive_region_list_adapter = TypeAdapter(list[InteractiveRegion])


class StatusResponse(_FrozenBaseModel):
    idle: bool


class ErrorResponse(_FrozenBaseModel):
    error_type: InstanceServerErrorType
    message: str


class MousePosition(_FrozenBaseModel):
    x: int
    y: int
