from __future__ import annotations

from enum import Enum
from typing import Literal, TypeAlias

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


ErrorType: TypeAlias = Literal["TIMEOUT", "INVALID_REQUEST", "UPSTREAM"]


class ErrorResponse(_BaseResponse):
    status: Literal[ResponseStatus.ERROR] = ResponseStatus.ERROR
    error_type: ErrorType
    message: str


Response: TypeAlias = ActionResponse | RewardResponse | ErrorResponse
ResponseAdapter: TypeAdapter[Response] = TypeAdapter(Response)
