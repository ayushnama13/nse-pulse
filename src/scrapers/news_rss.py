"""Generic RSS news scraper.

Pulls financial-news RSS feeds (Moneycontrol, ET Markets, Mint, NSE corporate
announcements). Each item is fingerprinted (sha256 of source|link) so re-runs
are idempotent. A symbol is best-effort extracted by matching company-name
keywords in the title against the bhavcopy symbol list.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any
from xml.etree import ElementTree as ET

from loguru import logger

from ..session import NSESession
from ..utils.archival import archive_payload


# Atom + RSS 2.0 both work; we parse minimally to stay dependency-free.
_DEFAULT_FEEDS: list[tuple[str, str]] = [
    ("moneycontrol_markets", "https://www.moneycontrol.com/rss/marketsnews.xml"),
    ("moneycontrol_business", "https://www.moneycontrol.com/rss/business.xml"),
    ("et_markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("livemint_markets", "https://www.livemint.com/rss/markets"),
    ("nse_announcements", "https://www.nseindia.com/api/corporate-announcements?index=equities"),
]


_DATE_FORMATS = (
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
)


def _parse_dt(s: str | None) -> datetime:
    if not s:
        return datetime.utcnow()
    s = s.strip()
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            # Strip tzinfo for SQLite naive datetime column.
            return dt.replace(tzinfo=None)
        except ValueError:
            continue
    return datetime.utcnow()


def _fingerprint(source: str, link: str) -> str:
    return hashlib.sha256(f"{source}|{link}".encode()).hexdigest()


def _detect_symbol(title: str, known: set[str]) -> str | None:
    """Naive symbol lift: exact uppercase token match against known symbols.

    Misses many real headlines that use long company names; we trade recall for
    precision so the symbol filter on the Ticker page isn't polluted.
    """
    if not known:
        return None
    tokens = re.findall(r"[A-Z][A-Z0-9&\-\.]{1,19}", title)
    for t in tokens:
        if t in known:
            return t
    return None


def _parse_rss(xml_bytes: bytes) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.warning("RSS parse error: {}", e)
        return []

    items: list[dict[str, Any]] = []
    # RSS 2.0
    for it in root.iter("item"):
        items.append({
            "title": (it.findtext("title") or "").strip(),
            "link": (it.findtext("link") or "").strip(),
            "summary": (it.findtext("description") or "").strip(),
            "pub": (it.findtext("pubDate") or ""),
        })
    if items:
        return items
    # Atom
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for it in root.findall("a:entry", ns):
        link_el = it.find("a:link", ns)
        items.append({
            "title": (it.findtext("a:title", default="", namespaces=ns) or "").strip(),
            "link": (link_el.attrib.get("href", "") if link_el is not None else ""),
            "summary": (it.findtext("a:summary", default="", namespaces=ns) or "").strip(),
            "pub": (it.findtext("a:updated", default="", namespaces=ns) or ""),
        })
    return items


def fetch_news(
    session: NSESession,
    feeds: list[tuple[str, str]] | None = None,
    known_symbols: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch all configured RSS feeds; return deduped news rows ready for insert_ignore."""
    feeds = feeds or _DEFAULT_FEEDS
    known_symbols = known_symbols or set()
    rows: list[dict[str, Any]] = []
    for source, url in feeds:
        try:
            raw = session.get(url, expect_json=False)
        except Exception as e:
            logger.warning("RSS fetch failed for {} ({}): {}", source, url, e)
            continue
        archive_payload(f"news/{source}", raw, extension="xml")
        for it in _parse_rss(raw):
            link = it["link"]
            if not link:
                continue
            sym = _detect_symbol(it["title"], known_symbols)
            rows.append({
                "source": source,
                "published_at": _parse_dt(it.get("pub")),
                "title": it["title"][:500],
                "link": link[:1000],
                "summary": (it.get("summary") or "")[:2000] or None,
                "symbol": sym,
                "fingerprint": _fingerprint(source, link),
            })
    logger.info("News RSS: {} items across {} feeds", len(rows), len(feeds))
    return rows
