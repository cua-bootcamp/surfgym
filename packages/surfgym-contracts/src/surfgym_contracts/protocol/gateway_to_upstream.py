from pydantic import BaseModel, ConfigDict, Field

from surfgym_contracts.task import Hook, Website


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AllocateRequest(_FrozenBaseModel):
    websites: list[Website] = Field(min_length=1)
    allocate_hooks: list[Hook]


class ReleaseRequest(_FrozenBaseModel):
    release_hooks: list[Hook]
