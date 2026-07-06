from typing import Annotated, Literal, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from surfgym_contracts.computer13 import Computer13


class _BaseRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
    )

    session_id: int
    task_id: str
    include_a11y: bool = False


class StartRequest(_BaseRequest):
    op: Literal["start"]


class ActionRequest(_BaseRequest):
    op: Literal["action"]
    actions: list[Computer13] = Field(min_length=1)


class RewardRequest(_BaseRequest):
    op: Literal["reward"]


AgentRequest: TypeAlias = Annotated[
    Union[StartRequest, ActionRequest, RewardRequest],
    Field(discriminator="op"),
]

AgentRequestAdapter: TypeAdapter[AgentRequest] = TypeAdapter(AgentRequest)
