from __future__ import annotations

from enum import Enum

from fastapi import status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, TypeAdapter


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class InstanceServerErrorType(str, Enum):
    INSTANCE_NOT_IDLE = "INSTANCE_NOT_IDLE"
    INSTANCE_IDLE = "INSTANCE_IDLE"
    INVALID_COMMAND = "INVALID_COMMAND"
    INVALID_INSTANCE_ID = "INVALID_INSTANCE_ID"
    CREATE_FAILED = "CREATE_FAILED"


_status_code_map: dict[InstanceServerErrorType, int] = {
    InstanceServerErrorType.INSTANCE_NOT_IDLE: status.HTTP_500_INTERNAL_SERVER_ERROR,
    InstanceServerErrorType.INSTANCE_IDLE: status.HTTP_500_INTERNAL_SERVER_ERROR,
    InstanceServerErrorType.INVALID_COMMAND: status.HTTP_400_BAD_REQUEST,
    InstanceServerErrorType.INVALID_INSTANCE_ID: status.HTTP_400_BAD_REQUEST,
    InstanceServerErrorType.CREATE_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


class GetInstanceResponse(_FrozenBaseModel):
    instance_id: str


class ScreenshotResponse(_FrozenBaseModel):
    snapshot_b64: str
    media_type: str
    x: float
    y: float


class ObservationResponse(_FrozenBaseModel):
    observation: list[str]


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


def error_response(error_type: InstanceServerErrorType, msg: str) -> JSONResponse:
    payload = ErrorResponse(error_type=error_type, message=msg)
    return JSONResponse(
        status_code=_status_code_map.get(error_type, status.HTTP_500_INTERNAL_SERVER_ERROR),
        content=payload.model_dump(),
    )


class MousePosition(_FrozenBaseModel):
    x: int
    y: int
