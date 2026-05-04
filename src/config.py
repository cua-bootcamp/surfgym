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
    pool_workers: int

    verl_timeout: float
    in_flight_timeout: float
    deadline_margin: float


class WavepoolConfig(FrozenBaseModel):
    host: str
    master_port: int
    master_workers: int
    instance_start_port: int
    instances: int

    viewport_width: int
    viewport_height: int


class Config(FrozenBaseModel):
    task_file_path: Path
    log_path: Path

    gateway_config: GatewayConfig = Field(alias="gateway")
    wavepool_config: WavepoolConfig = Field(alias="wavepool")
