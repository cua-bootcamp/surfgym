from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ResponseStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


class ImagePayload(_FrozenBaseModel):
    data: str = ""
    mime_type: str = Field(default="image/png", alias="mimeType")


class _BaseResponse(_FrozenBaseModel):
    session_id: int
    task_id: str


class ActionResponse(_BaseResponse):
    status: Literal[ResponseStatus.OK] = ResponseStatus.OK
    text: str | None = None
    image: ImagePayload


class RewardResponse(_BaseResponse):
    status: Literal[ResponseStatus.OK] = ResponseStatus.OK
    reward: float


class DEVRewardResponse(_BaseResponse):
    status: Literal[ResponseStatus.OK] = ResponseStatus.OK
    reward: float
    image: ImagePayload


type ErrorType = Literal["TIMEOUT", "INVALID_REQUEST", "UPSTREAM", "RETRYABLE", "UNEXPECTED"]


class ErrorResponse(_FrozenBaseModel):
    session_id: Any
    task_id: Any
    status: Literal[ResponseStatus.ERROR] = ResponseStatus.ERROR
    error_type: ErrorType
    message: str


type Response = ActionResponse | RewardResponse | ErrorResponse | DEVRewardResponse
ResponseAdapter: TypeAdapter[Response] = TypeAdapter(Response)
