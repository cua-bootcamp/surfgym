import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler


def get_logger(logger_name: str) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def setup_logging(logger: logging.Logger, log_path: Path) -> logging.Logger:
    if logger.handlers:
        return logger

    console_handler = RichHandler(rich_tracebacks=True)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file_path = log_path / run_id / "gateway.log"
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

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


surfgym_logger = get_logger("surfgym.gateway")
