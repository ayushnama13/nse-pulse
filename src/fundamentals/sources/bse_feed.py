"""
BSE source — STUB.

Phase 0 smoke test (2026-05-10) confirmed every endpoint under
api.bseindia.com/BseIndiaAPI/api/* returns the BSE Angular SPA shell HTML
instead of JSON, even known-historic endpoints (StockReachComp, BulkDeals,
DDR, BulkDealsNew). The host is no longer addressable from a plain
requests.Session; data appears gated behind a JS challenge or signed token.

See SOURCES_STATUS.md for full failure detail.

This stub:
  - logs `source='bse_feed', status='unhealthy'` to fetch_log so daily jobs
    can skip cleanly,
  - exposes `fetch_bulk_block_deals()` as a no-op that returns 0,
  - leaves `bulk_block_deals` table created (per spec) but empty.

Re-implementation plan (post-bootstrap):
  1. Use Playwright headless to load the BSE bulk-deals SPA, capture the XHRs
     it emits, and replay them with the full cookie set.
  2. Or: pull NSE bulk deals as a substitute (covers NSE-listed stocks).
"""
from __future__ import annotations

from .. import db
from ..utils.logger import get_logger

log = get_logger("bse_feed")

UNHEALTHY_REASON = (
    "BSE BseIndiaAPI subtree returns SPA shell HTML for all known endpoints "
    "(verified 2026-05-10). See stock/SOURCES_STATUS.md."
)


def fetch_bulk_block_deals() -> int:
    """Stub. Records unhealthy status to fetch_log and returns 0."""
    log.warning("BSE bulk/block deals: source unhealthy (see SOURCES_STATUS.md)")
    db.mark_unhealthy("bse_feed", UNHEALTHY_REASON)
    return 0


def fetch_corporate_actions() -> int:
    """Stub — same reason."""
    log.warning("BSE corporate actions: source unhealthy")
    db.mark_unhealthy("bse_feed_corp_actions", UNHEALTHY_REASON)
    return 0
