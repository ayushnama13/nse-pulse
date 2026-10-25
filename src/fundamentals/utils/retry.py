"""Tenacity-based retry decorator for network calls."""
from __future__ import annotations

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .logger import get_logger
from .. import config

_log = get_logger("retry")


_NET_ERRORS = (
    requests.exceptions.RequestException,
    ConnectionError,
    TimeoutError,
)


def network_retry(fn):
    """Apply standard exponential backoff retry to a network call."""
    return retry(
        stop=stop_after_attempt(config.RETRY_MAX),
        wait=wait_exponential(min=2, max=30),
        retry=retry_if_exception_type(_NET_ERRORS),
        before_sleep=before_sleep_log(_log, 30),  # WARNING
        reraise=True,
    )(fn)
