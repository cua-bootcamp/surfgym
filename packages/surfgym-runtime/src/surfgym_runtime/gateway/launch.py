import argparse
from pathlib import Path

import uvicorn

from surfgym_runtime.gateway.server import create_app
from surfgym_runtime.support import gateway_logger, load_config, setup_logging


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_path", type=Path)
    args = parser.parse_args()
    return args


def launch() -> None:
    args = _parse_args()
    config = load_config(args.config_path)
    setup_logging(gateway_logger, config.log_path, component="gateway")

    uvicorn.run(
        create_app(config),
        host=config.gateway_config.host,
        port=config.gateway_config.port,
    )


if __name__ == "__main__":
    launch()
