from __future__ import annotations

from enum import Enum

from fastapi import status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


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


class SnapshotResponse(_FrozenBaseModel):
    snapshot: PageSnapshot


class InteractiveTreeResponse(_FrozenBaseModel):
    mouse_position: MousePosition
    regions: dict[str, InteractiveRegion]


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


class DOMRectangle(_FrozenBaseModel):
    x: float
    y: float
    width: float
    height: float
    top: float
    right: float
    bottom: float
    left: float


class InteractiveRegion(_FrozenBaseModel):
    tag_name: str
    role: str
    aria_name: str
    v_scrollable: bool
    rects: list[DOMRectangle]


class ElementSnapshot(_FrozenBaseModel):
    tag_name: str = Field(alias="tagName")
    text: str
    text_content: str = Field(alias="textContent")
    html: str
    visible: bool
    attributes: dict[str, str]
    value: str
    checked: bool


class PageSnapshot(_FrozenBaseModel):
    url: str
    title: str
    text: str
    html: str
    elements: dict[str, list[ElementSnapshot]]
    selector_errors: dict[str, str]
