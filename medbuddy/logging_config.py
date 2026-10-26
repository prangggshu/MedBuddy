"""Application logging to the terminal and a rotating local log file."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging() -> None:
    logger = logging.getLogger("medbuddy")
    if getattr(logger, "_medbuddy_configured", False):
        return

    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        log_dir / "medbuddy.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.propagate = False
    logger._medbuddy_configured = True  # type: ignore[attr-defined]
