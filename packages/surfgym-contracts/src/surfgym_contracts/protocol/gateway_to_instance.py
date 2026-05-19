from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from surfgym_contracts.task import Action, Website


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GetInstanceRequest(_FrozenBaseModel):
    websites: list[Website] = Field(min_length=1)
    setup: Optional[Action]
