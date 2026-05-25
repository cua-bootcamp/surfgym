from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from surfgym_runtime.support.logger import setup_logging, surfgym_logger


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
    master_workers: int

    instance_start_port: int
    instances: int

    process_timeout: ProcessTimeout


class Config(FrozenBaseModel):
    task_file_path: Path
    log_path: Path

    gateway_config: GatewayConfig = Field(alias="gateway")
    wavepool_config: WavepoolConfig = Field(alias="wavepool")


def _validate_config(config: Config) -> None:
    gateway_config = config.gateway_config
    if gateway_config.gateway_workers < gateway_config.gateway_in_flight:
        surfgym_logger.warning(
            "Gateway max_workers (%s) is smaller than max_in_flight (%s). "
            "Requests may acquire in-flight slots faster than executor workers "
            "can process them, which can lead to queued HTTP sessions timing out. "
            "Consider setting max_workers >= max_in_flight.",
            gateway_config.gateway_workers,
            gateway_config.gateway_in_flight,
        )


def load_config(config_path: Path) -> Config:
    config = Config.model_validate_json(config_path.read_text())
    setup_logging(surfgym_logger, config.log_path)
    _validate_config(config)
    return config
