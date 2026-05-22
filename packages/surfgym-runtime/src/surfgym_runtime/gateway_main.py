"""
Entry point for running the SurfGym Gateway server.

- load and validate configuration
- run Gateway server
"""

import argparse
from pathlib import Path

import uvicorn

from surfgym_runtime.gateway.server import launch
from surfgym_runtime.support import Config, setup_logging, surfgym_logger


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


def _load_config(config_path: Path) -> Config:
    config = Config.model_validate_json(config_path.read_text())
    _validate_config(config)
    return config


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_path", type=Path)
    args = parser.parse_args()
    return args


def main() -> None:
    args = _parse_args()
    config = _load_config(args.config_path)
    setup_logging(surfgym_logger, config.log_path)

    try:
        uvicorn.run(
            launch(config), host=config.gateway_config.host, port=config.gateway_config.port
        )
    except Exception:
        surfgym_logger.exception("Unexpected gateway failure.")
        raise SystemExit()


if __name__ == "__main__":
    main()
