"""Telegram alerts. No-ops cleanly when disabled or unconfigured."""
from __future__ import annotations

import os

import requests
from loguru import logger

from .config import get_config


def send_alert(message: str) -> bool:
    cfg = get_config().get("alerts", {})
    if not cfg.get("enabled", False):
        return False
    channel = cfg.get("channel", "telegram")
    if channel != "telegram":
        logger.warning("Unsupported alert channel: {}", channel)
        return False

    tg = cfg.get("telegram", {})
    token = os.environ.get("NSE_TELEGRAM_BOT_TOKEN") or tg.get("bot_token") or ""
    chat_id = os.environ.get("NSE_TELEGRAM_CHAT_ID") or tg.get("chat_id") or ""
    if not token or not chat_id:
        logger.warning("Telegram alert requested but bot_token/chat_id not configured.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=10)
        if r.status_code != 200:
            logger.warning("Telegram alert failed: HTTP {} - {}", r.status_code, r.text[:200])
            return False
        return True
    except Exception as e:
        logger.warning("Telegram alert raised: {}", e)
        return False
