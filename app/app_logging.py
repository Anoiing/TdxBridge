from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.config import LOGS_DIR, ensure_runtime_dirs, get_config


def _build_timed_file_handler(path: Path) -> TimedRotatingFileHandler:
    config = get_config()
    return TimedRotatingFileHandler(
        path,
        when="midnight",
        backupCount=config.logging.retain_days,
        encoding="utf-8",
    )


def setup_logging() -> None:
    ensure_runtime_dirs()
    config = get_config()
    level_name = config.logging.level.upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    if getattr(root, "_tdxbridge_configured", False):
        root.setLevel(level)
        return

    root.handlers.clear()
    root.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    service_log = LOGS_DIR / "service.log"
    file_handler = _build_timed_file_handler(service_log)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    root._tdxbridge_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def get_json_logger(name: str, filename: str) -> logging.Logger:
    ensure_runtime_dirs()
    logger = logging.getLogger(name)
    if getattr(logger, "_tdxbridge_json_configured", False):
        return logger

    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = _build_timed_file_handler(LOGS_DIR / filename)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    logger._tdxbridge_json_configured = True  # type: ignore[attr-defined]
    return logger


def get_log_path(filename: str) -> Path:
    ensure_runtime_dirs()
    return LOGS_DIR / filename
