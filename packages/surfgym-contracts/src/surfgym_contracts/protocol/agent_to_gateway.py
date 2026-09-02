from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from surfgym_contracts.computer13 import Computer13
from surfgym_contracts.protocol.artifact import (
    MAX_ARTIFACT_BYTES,
    MAX_ARTIFACT_COUNT,
    ArtifactSpec,
)


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
    model_config = ConfigDict(frozen=True, extra="forbid")

    op: Literal["reward"]
    artifacts: list[ArtifactSpec] | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_ARTIFACT_COUNT,
    )

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null_artifacts(cls, value: object) -> object:
        if isinstance(value, dict) and "artifacts" in value and value["artifacts"] is None:
            raise ValueError("artifacts must be omitted or contain one to four items")
        return value

    @model_validator(mode="after")
    def validate_artifact_aggregate(self) -> "RewardRequest":
        if self.artifacts is not None and (
            sum(artifact.max_bytes for artifact in self.artifacts) > MAX_ARTIFACT_BYTES
        ):
            raise ValueError("artifact declared aggregate max_bytes exceeds 4 MiB")
        return self


type AgentRequest = Annotated[
    Union[StartRequest, ActionRequest, RewardRequest],
    Field(discriminator="op"),
]

AgentRequestAdapter: TypeAdapter[AgentRequest] = TypeAdapter(AgentRequest)
