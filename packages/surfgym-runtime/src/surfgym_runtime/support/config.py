from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

DOCKER_ARTIFACT_CONTROL_TIMEOUT_SECONDS = 35.0


class FrozenBaseModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class GatewayConfig(FrozenBaseModel):
    host: str
    port: int
    gateway_workers: int
    gateway_in_flight: int

    verl_timeout: float
    artifact_reward_timeout: float = Field(strict=True, gt=0, allow_inf_nan=False)
    in_flight_timeout: float
    deadline_margin: float

    @model_validator(mode="after")
    def validate_artifact_reward_timeout(self) -> "GatewayConfig":
        if self.artifact_reward_timeout < self.verl_timeout:
            raise ValueError(
                "gateway.artifact_reward_timeout must be greater than or equal to "
                "gateway.verl_timeout"
            )
        return self


class ProcessTimeout(FrozenBaseModel):
    allocate: float
    release: float
    screenshot: float
    observe: float
    execute: float

    layer_gap: float


class WavepoolConfig(FrozenBaseModel):
    host: str
    master_port: int

    instance_start_port: int
    instances: int
    contexts_per_instance: int

    process_timeout: ProcessTimeout


class Config(FrozenBaseModel):
    task_file_path: Path
    log_path: Path

    gateway_config: GatewayConfig = Field(alias="gateway")
    wavepool_config: WavepoolConfig = Field(alias="wavepool")

    @model_validator(mode="after")
    def validate_artifact_reward_budget(self) -> "Config":
        usable_timeout = (
            self.gateway_config.artifact_reward_timeout - self.gateway_config.deadline_margin
        )
        required_timeout = (
            DOCKER_ARTIFACT_CONTROL_TIMEOUT_SECONDS + self.wavepool_config.process_timeout.layer_gap
        )
        if usable_timeout < required_timeout:
            raise ValueError(
                "gateway.artifact_reward_timeout minus gateway.deadline_margin must leave "
                "at least 35 seconds plus wavepool.process_timeout.layer_gap"
            )
        return self


# def _validate_config(config: Config) -> None:
#     gateway_config = config.gateway_config
#     if gateway_config.gateway_workers < gateway_config.gateway_in_flight:
#         raise ValueError(
#             f"""
# Gateway max_workers ({config.gateway_config.gateway_workers}) is smaller than max_in_flight ({config.gateway_config.gateway_in_flight}).
# Please set gateway_workers larger than gateway_in_flight to avoid in-flight timeout.
# """.strip()
#         )


def load_config(config_path: Path) -> Config:
    config = Config.model_validate_json(config_path.read_text())
    # _validate_config(config)
    return config
