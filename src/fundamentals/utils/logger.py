"""Per-source rotating file loggers + console handler at INFO."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .. import config

_FMT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_configured: dict[str, logging.Logger] = {}


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger that writes:
      - console at LOG_LEVEL_CONSOLE (default INFO)
      - logs/<name>.log at LOG_LEVEL_FILE (default DEBUG), rotating 5x5MB
    """
    if name in _configured:
        return _configured[name]

    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    log.propagate = False

    fmt = logging.Formatter(_FMT)

    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, config.LOG_LEVEL_CONSOLE.upper(), logging.INFO))
    ch.setFormatter(fmt)
    log.addHandler(ch)

    log_file = config.LOG_DIR / f"{name}.log"
    fh = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=5)
    fh.setLevel(getattr(logging, config.LOG_LEVEL_FILE.upper(), logging.DEBUG))
    fh.setFormatter(fmt)
    log.addHandler(fh)

    _configured[name] = log
    return log
