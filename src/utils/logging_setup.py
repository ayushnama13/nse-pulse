"""Loguru sink configuration. Per-day rotating log file + console summary."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from loguru import logger

from .config import get_config, resolve_path


_INITIALIZED = False


def setup_logging(run_date: date | None = None) -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    cfg = get_config().get("logging", {})
    level = cfg.get("level", "INFO")
    log_dir = resolve_path(cfg.get("log_dir", "./logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    run_date = run_date or date.today()
    pattern = cfg.get("log_file_pattern", "{date}.log").replace("{date}", run_date.isoformat())
    log_path = log_dir / pattern

    logger.remove()
    logger.add(
        log_path,
        level=level,
        rotation=None,
        enqueue=True,
        backtrace=False,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    )
    if cfg.get("console_summary_only", True):
        logger.add(sys.stderr, level="WARNING", format="{level} | {message}")
    else:
        logger.add(sys.stderr, level=level, format="{level} | {message}")
    _INITIALIZED = True
