"""HTTP session factories with proper headers / cookie warmup."""
from __future__ import annotations

import time

import requests

from .. import config
from .logger import get_logger

_log = get_logger("http")


def get_nse_session() -> requests.Session:
    """NSE blocks default UAs; warm cookies on www.nseindia.com first."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    try:
        s.get("https://www.nseindia.com/", timeout=config.HTTP_TIMEOUT)
        time.sleep(0.8)
    except requests.RequestException as e:
        _log.warning("NSE warmup failed: %s", e)
    return s


def get_bse_session() -> requests.Session:
    """BSE requires Origin/Referer headers. Currently the BseIndiaAPI subtree is gated; see SOURCES_STATUS.md."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.bseindia.com/",
        "Origin": "https://www.bseindia.com",
        "Connection": "keep-alive",
    })
    return s


def get_screener_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s
