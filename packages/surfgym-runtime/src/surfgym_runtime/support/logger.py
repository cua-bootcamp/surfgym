import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler


def _get_logger() -> logging.Logger:
    logger = logging.getLogger("surfgym")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger


def _has_handler(logger: logging.Logger, handler_type: type[logging.Handler]) -> bool:
    return any(isinstance(handler, handler_type) for handler in logger.handlers)


def _setup_console_handler(logger: logging.Logger) -> logging.Logger:
    if _has_handler(logger, RichHandler):
        return logger

    console_handler = RichHandler(rich_tracebacks=True)
    console_handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))

    logger.addHandler(console_handler)
    return logger


def _setup_file_logger(
    log_path: Path,
) -> None:
    logger = _get_logger()
    if _has_handler(logger, RotatingFileHandler):
        return

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file_path = log_path / run_id / "surfgyml.log"
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )

    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(file_handler)


logger = _setup_console_handler(_get_logger())


def setup_logging(
    log_path: Path,
) -> None:
    _setup_file_logger(log_path=log_path)
