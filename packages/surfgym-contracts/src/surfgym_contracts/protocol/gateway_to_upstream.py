from pydantic import BaseModel, ConfigDict, Field

from surfgym_contracts.command import Command
from surfgym_contracts.task import Criteria, Hook, Website


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


#############################
#      Gateway > Master     #
#############################


class GatewayAllocateRequest(_FrozenBaseModel):
    websites: list[Website] = Field(min_length=1)
    hooks: list[Hook]
    release_hooks: list[Hook] = Field(default_factory=lambda: list[Hook]())


class GatewayReleaseRequest(_FrozenBaseModel):
    hooks: list[Hook]


##############################
#      Master > Instance     #
##############################


MasterAllocateRequest = GatewayAllocateRequest

MasterReleaseRequest = GatewayReleaseRequest


#############################
#     Gateway > Instance    #
#############################


class ExecuteRequest(_FrozenBaseModel):
    command: Command


class ObserveRequest(_FrozenBaseModel):
    criteria: list[Criteria]
    hooks: list[Hook]


class ScreenshotRequest(_FrozenBaseModel):
    pass


class LiveContextsResponse(_FrozenBaseModel):
    context_ids: tuple[str, ...]
