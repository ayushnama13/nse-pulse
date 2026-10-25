"""Health-check report.

Returns a dict per scraper: last-success time, last-failure time, rows fetched,
and an overall status. Powers a `/healthz` console output (for systemd watchers)
and the Data Quality page in the dashboard.

Run as:
    python -m src.utils.healthz                 # plain-text report
    python -m src.utils.healthz --json          # JSON
    python -m src.utils.healthz --exit-on-stale # exit 2 if any scraper is stale > 24h
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from ..storage.database import init_db, session_scope
from ..storage.models import ScraperRun


_STALE_HOURS = 36  # one weekday + buffer


def build_report() -> dict[str, Any]:
    init_db()
    out: dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "scrapers": {},
        "status": "ok",
    }
    with session_scope() as s:
        names = [r[0] for r in s.execute(select(ScraperRun.scraper).distinct()).all()]
        for name in names:
            last_ok = s.execute(
                select(ScraperRun).where(
                    ScraperRun.scraper == name,
                    ScraperRun.status == "success",
                ).order_by(ScraperRun.run_finished_at.desc()).limit(1)
            ).scalar_one_or_none()
            last_fail = s.execute(
                select(ScraperRun).where(
                    ScraperRun.scraper == name,
                    ScraperRun.status == "failure",
                ).order_by(ScraperRun.run_finished_at.desc()).limit(1)
            ).scalar_one_or_none()
            total_runs = s.execute(
                select(func.count()).select_from(ScraperRun)
                .where(ScraperRun.scraper == name)
            ).scalar() or 0

            entry = {
                "last_success_at": _ts(last_ok),
                "last_failure_at": _ts(last_fail),
                "last_rows_fetched": last_ok.rows_fetched if last_ok else None,
                "last_rows_stored": last_ok.rows_stored if last_ok else None,
                "last_error": (last_fail.error[:300] if last_fail and last_fail.error else None),
                "total_runs": total_runs,
            }

            if last_ok is None or (
                last_ok.run_finished_at
                and last_ok.run_finished_at < datetime.utcnow() - timedelta(hours=_STALE_HOURS)
            ):
                entry["status"] = "stale"
                out["status"] = "degraded"
            elif last_fail and last_ok and last_fail.run_finished_at > last_ok.run_finished_at:
                entry["status"] = "failing"
                out["status"] = "degraded"
            else:
                entry["status"] = "ok"

            out["scrapers"][name] = entry

    return out


def _ts(run: ScraperRun | None) -> str | None:
    if not run or not run.run_finished_at:
        return None
    return run.run_finished_at.isoformat(timespec="seconds") + "Z"


def cli() -> None:
    p = argparse.ArgumentParser(description="NSE Pulse health report")
    p.add_argument("--json", action="store_true")
    p.add_argument("--exit-on-stale", action="store_true",
                   help="Exit 2 if any scraper is stale or failing")
    args = p.parse_args()

    rep = build_report()
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        print(f"NSE Pulse health  ({rep['generated_at']})  overall={rep['status']}")
        if not rep["scrapers"]:
            print("  (no scraper runs recorded yet)")
        for name, entry in sorted(rep["scrapers"].items()):
            print(f"  - {name:<20} {entry['status']:<8} "
                  f"last_ok={entry['last_success_at'] or '-':<22} "
                  f"rows={entry['last_rows_stored'] or 0}")
    if args.exit_on_stale and rep["status"] != "ok":
        sys.exit(2)


if __name__ == "__main__":
    cli()
