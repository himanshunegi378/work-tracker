"""Rotating-file logging shared by the GUI and the CLI."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from src.runtime_paths import log_file_path

logger = logging.getLogger(__name__)


def configure_logging(log_path: Optional[Path] = None) -> str:
    """Configure app logging to a rotating file for later analysis."""
    resolved_log_path = Path(log_path or log_file_path())
    resolved_log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    if not any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", "") == str(resolved_log_path.resolve())
        for handler in root_logger.handlers
    ):
        file_handler = RotatingFileHandler(
            resolved_log_path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s"
            )
        )
        root_logger.addHandler(file_handler)

    logger.info("Application logging configured at %s", resolved_log_path.resolve())
    return str(resolved_log_path)
