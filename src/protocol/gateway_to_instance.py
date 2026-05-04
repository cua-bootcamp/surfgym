from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from src.protocol.command import Command


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class InstanceOp(str, Enum):
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
    pass


class AllocateRequest(_BaseRequest):
    op: Literal[InstanceOp.ALLOCATE] = InstanceOp.ALLOCATE
    lifetime_mins: int = Field(default=120, ge=1)


class ReleaseRequest(_BaseRequest):
    op: Literal[InstanceOp.RELEASE] = InstanceOp.RELEASE
    instance: InstanceRef


class ExecuteRequest(_BaseRequest):
    op: Literal[InstanceOp.EXECUTE] = InstanceOp.EXECUTE
    instance: InstanceRef
    command: Command


class ScreenshotRequest(_BaseRequest):
    op: Literal[InstanceOp.SCREENSHOT] = InstanceOp.SCREENSHOT
    instance: InstanceRef
    interaction_mode: InteractionMode = InteractionMode.COORDINATE


class MetadataRequest(_BaseRequest):
    op: Literal[InstanceOp.METADATA] = InstanceOp.METADATA
    instance: InstanceRef


class ProbeRequest(_BaseRequest):
    op: Literal[InstanceOp.PROBE] = InstanceOp.PROBE
    instance: InstanceRef


InstanceRequest = Annotated[
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

InstanceRequestAdapter: TypeAdapter[InstanceRequest] = TypeAdapter(InstanceRequest)
