from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from src.omnibox.protocol.omnibox_command import OmniboxCommand


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OmniboxOp(str, Enum):
    ALLOCATE = "allocate"
    RELEASE = "release"
    EXECUTE = "execute"
    SCREENSHOT = "screenshot"
    METADATA = "metadata"
    PROBE = "probe"


class InteractionMode(str, Enum):
    COORDINATE = "coordinate"
    SET_OF_MARKS = "set_of_marks"


class InstanceRef(_FrozenBaseModel):
    instance_id: str
    node: str


class _BaseRequest(_FrozenBaseModel):
    op: OmniboxOp


class AllocateRequest(_BaseRequest):
    op: Literal[OmniboxOp.ALLOCATE] = OmniboxOp.ALLOCATE
    lifetime_mins: int = Field(default=120, ge=1)


class ReleaseRequest(_BaseRequest):
    op: Literal[OmniboxOp.RELEASE] = OmniboxOp.RELEASE
    instance: InstanceRef


class ExecuteRequest(_BaseRequest):
    op: Literal[OmniboxOp.EXECUTE] = OmniboxOp.EXECUTE
    instance: InstanceRef
    command: OmniboxCommand


class ScreenshotRequest(_BaseRequest):
    op: Literal[OmniboxOp.SCREENSHOT] = OmniboxOp.SCREENSHOT
    instance: InstanceRef
    interaction_mode: InteractionMode = InteractionMode.COORDINATE


class MetadataRequest(_BaseRequest):
    op: Literal[OmniboxOp.METADATA] = OmniboxOp.METADATA
    instance: InstanceRef


class ProbeRequest(_BaseRequest):
    op: Literal[OmniboxOp.PROBE] = OmniboxOp.PROBE
    instance: InstanceRef


OmniboxRequest = Annotated[
    Union[
        AllocateRequest,
        ReleaseRequest,
        ExecuteRequest,
        ScreenshotRequest,
        MetadataRequest,
        ProbeRequest,
    ],
    Field(discriminator="op"),
]

OmniboxRequestAdapter = TypeAdapter(OmniboxRequest)
