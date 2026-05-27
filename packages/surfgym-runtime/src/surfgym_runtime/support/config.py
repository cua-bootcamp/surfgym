from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


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
    in_flight_timeout: float
    deadline_margin: float


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
