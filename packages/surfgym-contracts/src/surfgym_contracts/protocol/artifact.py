from __future__ import annotations

import base64
import binascii
import hashlib
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_ARTIFACT_COUNT = 4
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_PATH_BYTES = 512
MAX_ARTIFACT_PATH_COMPONENTS = 64
MAX_ARTIFACT_COMPONENT_BYTES = 255
MAX_ARTIFACT_BASE64_LENGTH = ((MAX_ARTIFACT_BYTES + 2) // 3) * 4
ARTIFACT_MIME_TYPE_PATTERN = r"^[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+$"


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")


def _validate_artifact_path(value: str) -> str:
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("path must be valid UTF-8") from exc

    if (
        not value
        or len(encoded) > MAX_ARTIFACT_PATH_BYTES
        or value.startswith("/")
        or value.endswith("/")
        or "//" in value
        or "\\" in value
        or ":" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError("path must be a canonical relative POSIX path")

    components = value.split("/")
    if len(components) > MAX_ARTIFACT_PATH_COMPONENTS or any(
        component in {"", ".", ".."}
        or len(component.encode("utf-8")) > MAX_ARTIFACT_COMPONENT_BYTES
        for component in components
    ):
        raise ValueError("path contains invalid components")
    return value


class ArtifactSpec(_FrozenBaseModel):
    path: str = Field(strict=True)
    max_bytes: int = Field(strict=True, ge=1, le=MAX_ARTIFACT_BYTES)

    _validate_path = field_validator("path")(_validate_artifact_path)


class ArtifactPayload(_FrozenBaseModel):
    path: str = Field(strict=True)
    mime_type: str = Field(
        strict=True,
        min_length=1,
        max_length=255,
        pattern=ARTIFACT_MIME_TYPE_PATTERN,
    )
    sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    size: int = Field(strict=True, ge=0, le=MAX_ARTIFACT_BYTES)
    encoding: Literal["base64"]
    data: str = Field(strict=True, max_length=MAX_ARTIFACT_BASE64_LENGTH)

    _validate_path = field_validator("path")(_validate_artifact_path)

    @model_validator(mode="after")
    def validate_encoded_content(self) -> Self:
        try:
            raw = base64.b64decode(self.data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("artifact data must be valid base64") from exc
        if base64.b64encode(raw).decode("ascii") != self.data:
            raise ValueError("artifact data must use canonical base64 encoding")
        if len(raw) != self.size:
            raise ValueError("artifact size does not match decoded data")
        if hashlib.sha256(raw).hexdigest() != self.sha256:
            raise ValueError("artifact sha256 does not match decoded data")
        return self
