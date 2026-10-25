"""Alert sinks: telegram, email, discord, webhook. All take (subject, body)."""
from __future__ import annotations

import json
import os
import smtplib
from email.mime.text import MIMEText

import requests
from loguru import logger

from ..utils.config import get_config


def _telegram(subject: str, body: str) -> bool:
    cfg = get_config().get("alerts", {}).get("telegram", {})
    token = os.environ.get("NSE_TELEGRAM_BOT_TOKEN") or cfg.get("bot_token") or ""
    chat_id = os.environ.get("NSE_TELEGRAM_CHAT_ID") or cfg.get("chat_id") or ""
    if not token or not chat_id:
        logger.warning("Telegram sink: bot_token/chat_id not set")
        return False
    msg = f"*{subject}*\n{body}"[:4000]
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        logger.warning("Telegram sink error: {}", e)
        return False


def _email(subject: str, body: str) -> bool:
    host = os.environ.get("NSE_ALERT_EMAIL_SMTP_HOST")
    port = int(os.environ.get("NSE_ALERT_EMAIL_SMTP_PORT") or 587)
    user = os.environ.get("NSE_ALERT_EMAIL_USERNAME") or ""
    pw = os.environ.get("NSE_ALERT_EMAIL_PASSWORD") or ""
    sender = os.environ.get("NSE_ALERT_EMAIL_FROM") or user
    to = os.environ.get("NSE_ALERT_EMAIL_TO") or ""
    if not (host and to):
        logger.warning("Email sink: NSE_ALERT_EMAIL_SMTP_HOST / NSE_ALERT_EMAIL_TO not set")
        return False
    try:
        msg = MIMEText(body)
        msg["Subject"] = f"[NSE Pulse] {subject}"
        msg["From"] = sender
        msg["To"] = to
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            if user:
                smtp.login(user, pw)
            smtp.sendmail(sender, [a.strip() for a in to.split(",")], msg.as_string())
        return True
    except Exception as e:
        logger.warning("Email sink error: {}", e)
        return False


def _discord(subject: str, body: str) -> bool:
    url = os.environ.get("NSE_DISCORD_WEBHOOK_URL") or ""
    if not url:
        logger.warning("Discord sink: NSE_DISCORD_WEBHOOK_URL not set")
        return False
    try:
        r = requests.post(
            url,
            json={"content": f"**{subject}**\n{body}"[:1900]},
            timeout=10,
        )
        return r.status_code in (200, 204)
    except Exception as e:
        logger.warning("Discord sink error: {}", e)
        return False


def _webhook(subject: str, body: str) -> bool:
    url = os.environ.get("NSE_WEBHOOK_URL") or ""
    if not url:
        logger.warning("Webhook sink: NSE_WEBHOOK_URL not set")
        return False
    try:
        r = requests.post(url, data=json.dumps({"subject": subject, "body": body}),
                          headers={"Content-Type": "application/json"}, timeout=10)
        return r.status_code < 400
    except Exception as e:
        logger.warning("Webhook sink error: {}", e)
        return False


def _log_only(subject: str, body: str) -> bool:
    logger.info("ALERT [{}]: {}", subject, body[:300])
    return True


_REGISTRY = {
    "telegram": _telegram,
    "email": _email,
    "discord": _discord,
    "webhook": _webhook,
    "log": _log_only,
}


def available_sinks() -> list[str]:
    return list(_REGISTRY)


def dispatch(sinks: list[str], subject: str, body: str) -> tuple[bool, str | None]:
    """Send `subject`/`body` to every sink in `sinks`. Returns (all_ok, last_error)."""
    if not sinks:
        sinks = ["log"]
    ok = True
    err: str | None = None
    for s in sinks:
        s = s.strip().lower()
        fn = _REGISTRY.get(s)
        if fn is None:
            logger.warning("Unknown alert sink: {}", s)
            ok = False
            err = f"unknown sink: {s}"
            continue
        success = False
        try:
            success = fn(subject, body)
        except Exception as e:
            err = str(e)
        if not success:
            ok = False
    return ok, err
