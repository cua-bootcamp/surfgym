from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from surfgym_contracts.protocol.artifact import MAX_ARTIFACT_COUNT, ArtifactPayload


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
    image: Optional[ImagePayload] = None


class RewardBundleResponse(RewardResponse):
    artifacts: list[ArtifactPayload] = Field(
        min_length=1,
        max_length=MAX_ARTIFACT_COUNT,
    )


type ErrorType = Literal["TIMEOUT", "INVALID_REQUEST", "UPSTREAM", "RETRYABLE", "UNEXPECTED"]


class ErrorResponse(_FrozenBaseModel):
    session_id: Any
    task_id: Any
    status: Literal[ResponseStatus.ERROR] = ResponseStatus.ERROR
    error_type: ErrorType
    message: str


type Response = ActionResponse | RewardBundleResponse | RewardResponse | ErrorResponse
ResponseAdapter: TypeAdapter[Response] = TypeAdapter(Response)
