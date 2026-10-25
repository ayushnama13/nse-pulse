"""Raw-payload archival + schema-drift detection.

After every scraper call, we keep a gzipped copy of the raw response under
`data/raw/{scraper}/{YYYY}/{MM}/{YYYY-MM-DD}.{ext}.gz` for ~30 days. This lets
us re-derive features after a bug fix without re-scraping (and saves us from
NSE's 30 req/min cap during debugging).

We also fingerprint the response shape (sorted top-level + first-row keys) and
flag drift — useful early-warning when NSE renames a field (the UDiFF bhavcopy
migration broke many scrapers; this would catch the next one on day 1).
"""
from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from .config import resolve_path

_DEFAULT_ROOT = "./data/raw"
_RETENTION_DAYS = 30


def _root() -> Path:
    return resolve_path(_DEFAULT_ROOT)


def archive_payload(
    scraper: str,
    payload: bytes | str | dict | list,
    *,
    run_date: date | None = None,
    extension: str = "json",
) -> Path:
    """Persist the raw payload. Safe to call from any scraper.

    Returns the path written. Errors are logged, not raised, so a disk-full
    condition cannot fail the pipeline.
    """
    run_date = run_date or date.today()
    try:
        d = _root() / scraper / f"{run_date.year:04d}" / f"{run_date.month:02d}"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{run_date.isoformat()}.{extension}.gz"

        if isinstance(payload, (dict, list)):
            data: bytes = json.dumps(payload, default=str).encode("utf-8")
        elif isinstance(payload, str):
            data = payload.encode("utf-8")
        else:
            data = payload

        with gzip.open(path, "wb", compresslevel=6) as f:
            f.write(data)
        return path
    except Exception as e:
        logger.warning("Failed to archive {} payload: {}", scraper, e)
        return Path("/dev/null")


def schema_fingerprint(payload: Any) -> str:
    """Stable hash of the schema shape (key sets), not the values.

    For dicts: sorted keys.
    For lists: schema of first item (if dict), else type-name.
    Returns SHA-256 hex.
    """
    sig = _shape(payload)
    return hashlib.sha256(json.dumps(sig, sort_keys=True).encode()).hexdigest()


def _shape(obj: Any, depth: int = 0, max_depth: int = 3) -> Any:
    if depth >= max_depth:
        return type(obj).__name__
    if isinstance(obj, dict):
        return {k: _shape(v, depth + 1, max_depth) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        if not obj:
            return ["empty"]
        return [_shape(obj[0], depth + 1, max_depth)]
    return type(obj).__name__


def check_drift(scraper: str, payload: Any, *, store: Path | None = None) -> bool:
    """Compare current payload schema to the last-seen one for this scraper.

    Returns True if drift is detected. Stores the new fingerprint on either
    first-seen or drift. Drift triggers a WARNING log — the caller decides
    whether to send an alert.
    """
    store = store or (_root() / "_fingerprints.json")
    store.parent.mkdir(parents=True, exist_ok=True)

    fp = schema_fingerprint(payload)
    prev: dict[str, str] = {}
    if store.exists():
        try:
            prev = json.loads(store.read_text())
        except Exception:
            prev = {}

    last = prev.get(scraper)
    if last is None:
        prev[scraper] = fp
        store.write_text(json.dumps(prev, indent=2, sort_keys=True))
        logger.info("Schema fingerprint for {} stored (first seen)", scraper)
        return False

    if last != fp:
        logger.warning(
            "SCHEMA DRIFT detected for {}: was {}, now {}. "
            "Inspect raw payload under data/raw/{}/ before trusting downstream data.",
            scraper, last[:12], fp[:12], scraper,
        )
        prev[scraper] = fp
        store.write_text(json.dumps(prev, indent=2, sort_keys=True))
        return True
    return False


def prune_old(retention_days: int = _RETENTION_DAYS) -> int:
    """Delete archived payloads older than `retention_days`. Returns count deleted."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = 0
    root = _root()
    if not root.exists():
        return 0
    for path in root.rglob("*.gz"):
        try:
            if datetime.utcfromtimestamp(path.stat().st_mtime) < cutoff:
                path.unlink()
                deleted += 1
        except OSError:
            continue
    if deleted:
        logger.info("Pruned {} archived payloads older than {}d", deleted, retention_days)
    return deleted


def list_archived(scraper: str | None = None) -> Iterable[Path]:
    root = _root() if scraper is None else _root() / scraper
    if not root.exists():
        return []
    return sorted(root.rglob("*.gz"))
