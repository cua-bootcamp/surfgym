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
    allocate_hooks: list[Hook]


class GatewayReleaseRequest(_FrozenBaseModel):
    release_hooks: list[Hook]


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
    observe_hooks: list[Hook]


class ScreenshotRequest(_FrozenBaseModel):
    pass
