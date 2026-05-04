from __future__ import annotations

from enum import Enum

from fastapi import status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MasterServerErrorType(str, Enum):
    NO_INSTANCES_AVAILABLE = "NO_INSTANCES_AVAILABLE"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"


_status_code_map: dict[MasterServerErrorType, int] = {
    MasterServerErrorType.NO_INSTANCES_AVAILABLE: status.HTTP_500_INTERNAL_SERVER_ERROR,
    MasterServerErrorType.INVALID_PAYLOAD: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


class GetInstanceResponse(_FrozenBaseModel):
    instance_id: str
    instance_host: str
    instance_port: int


class ErrorResponse(_FrozenBaseModel):
    error_type: MasterServerErrorType
    message: str


def error_response(error_type: MasterServerErrorType, msg: str) -> JSONResponse:
    payload = ErrorResponse(error_type=error_type, message=msg)
    return JSONResponse(
        status_code=_status_code_map.get(error_type, status.HTTP_500_INTERNAL_SERVER_ERROR),
        content=payload.model_dump(),
    )
