from pydantic import BaseModel, ConfigDict, Field

from surfgym_contracts.task import Hook, Website


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GatewayAllocateRequest(_FrozenBaseModel):
    websites: list[Website] = Field(min_length=1)
    allocate_hooks: list[Hook]


class GatewayReleaseRequest(_FrozenBaseModel):
    release_hooks: list[Hook]


MasterAllocateRequest = GatewayAllocateRequest

MasterReleaseRequest = GatewayReleaseRequest
