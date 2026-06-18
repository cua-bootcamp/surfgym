from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from surfgym_contracts.task import Action, ProfileSetup, Website


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AllocateRequest(_FrozenBaseModel):
    websites: list[Website] = Field(min_length=1)
    setup: Optional[list[Action]]
    profile_setup: Optional[ProfileSetup] = None
