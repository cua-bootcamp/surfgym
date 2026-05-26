import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler


def _log_timestamp() -> str:
    return os.environ.get("SURFGYM_LOG_STAMP") or datetime.now().strftime("%Y%m%d-%H%M%S")


def get_logger(logger_name: str) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def _point_latest(log_file_path: Path) -> None:
    latest_path = log_file_path.parent / "latest.log"

    try:
        if latest_path.exists() or latest_path.is_symlink():
            latest_path.unlink()
        latest_path.symlink_to(log_file_path.name)
    except OSError:
        pass


def setup_logging(
    logger: logging.Logger,
    log_path: Path,
    *,
    component: str,
    console: bool = True,
    file: bool = True,
) -> logging.Logger:
    if logger.handlers:
        return logger

    if console:
        console_handler = RichHandler(rich_tracebacks=True)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
        logger.addHandler(console_handler)

    if file:
        log_file_name = f"{_log_timestamp()}.log"
        log_file_path = log_path / component / log_file_name
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(file_handler)
        _point_latest(log_file_path)

    return logger


gateway_logger = get_logger("surfgym.gateway")
deploy_logger = get_logger("surfgym.wavepool.deploy")
master_logger = get_logger("surfgym.wavepool.master")
instance_logger = get_logger("surfgym.wavepool.instance")
