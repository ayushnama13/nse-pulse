"""Fetch and load NSE corporate events, FII/DII flow, and deal data."""
from __future__ import annotations

import argparse
import logging
import random
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scrapers.event_loaders import (  # noqa: E402
    parse_announcements,
    parse_board_meetings,
    parse_deals,
    parse_financial_results,
    parse_fii_dii,
)
from src.session import NSESession  # noqa: E402

API = "https://www.nseindia.com/api/"
ARCHIVE = "https://nsearchives.nseindia.com/content/equities/"
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "nse.db"
LOG = logging.getLogger("load_nse_events")


def upsert_rows(connection: sqlite3.Connection, table: str, rows: list[dict], conflict: tuple[str, ...],
                update: tuple[str, ...]) -> int:
    if not rows:
        return 0
    columns = tuple(rows[0])
    placeholders = ", ".join("?" for _ in columns)
    names = ", ".join(f'"{column}"' for column in columns)
    conflict_sql = ", ".join(f'"{column}"' for column in conflict)
    update_sql = ", ".join(f'"{column}"=excluded."{column}"' for column in update)
    action = f"DO UPDATE SET {update_sql}" if update_sql else "DO NOTHING"
    sql = f'INSERT INTO "{table}" ({names}) VALUES ({placeholders}) ON CONFLICT ({conflict_sql}) {action}'
    connection.executemany(sql, [tuple(row.get(column) for column in columns) for row in rows])
    connection.commit()
    return len(rows)


def _request(session: NSESession, action: Callable[[], object], state: dict[str, int]) -> object | None:
    try:
        result = action()
    except Exception as exc:  # one NSE endpoint failure must not stop other windows
        state["failures"] += 1
        LOG.warning("NSE request failed (%d consecutive): %s", state["failures"], exc)
        if state["failures"] >= 5:
            raise RuntimeError("aborting after five consecutive NSE request failures") from exc
        return None
    state["failures"] = 0
    return result


def _pause() -> None:
    time.sleep(random.uniform(2.0, 3.0))


def _range_window(start: date, end: date):
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=2), end)
        yield cursor, window_end
        cursor = window_end + timedelta(days=1)


def _open_db(dry_run: bool) -> sqlite3.Connection | None:
    if dry_run:
        return None
    connection = sqlite3.connect(DB_PATH, timeout=60)
    connection.execute("PRAGMA busy_timeout = 60000")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _write(connection: sqlite3.Connection | None, table: str, rows: list[dict], conflict: tuple[str, ...],
           update: tuple[str, ...]) -> int:
    if connection is None:
        return len(rows)
    return upsert_rows(connection, table, rows, conflict, update)


def run_one(command: str, args: argparse.Namespace, session: NSESession,
            connection: sqlite3.Connection | None, state: dict[str, int]) -> int:
    count = 0
    if command == "announcements":
        end = date.today()
        start = _parse_cli_date(args.from_date) if args.from_date else end - timedelta(days=args.days - 1)
        last = _parse_cli_date(args.to_date) if args.to_date else end
        if start > last:
            raise ValueError("--from must be on or before --to")
        for first, final in _range_window(start, last):
            payload = _request(session, lambda: session.get(
                API + "corporate-announcements",
                params={"index": "equities", "from_date": first.strftime("%d-%m-%Y"),
                        "to_date": final.strftime("%d-%m-%Y")}), state)
            if payload is not None:
                rows = parse_announcements(payload)
                count += _write(connection, "announcements", rows,
                                ("symbol", "broadcast_date", "subject"),
                                ("company_name", "description", "attachment_link"))
            _pause()
    elif command == "board-meetings":
        payload = _request(session, lambda: session.get(API + "corporate-board-meetings", params={"index": "equities"}), state)
        if payload is not None:
            rows = parse_board_meetings(payload)
            count = _write(connection, "board_meetings", rows, ("symbol", "meeting_date", "purpose"),
                           ("company_name", "details"))
    elif command == "results":
        for period in args.period:
            params = {"index": "equities", "period": period}
            if args.from_date:
                params["from_date"] = _parse_cli_date(args.from_date).strftime("%d-%m-%Y")
            if args.to_date:
                params["to_date"] = _parse_cli_date(args.to_date).strftime("%d-%m-%Y")
            payload = _request(session, lambda p=params: session.get(API + "corporates-financial-results", params=p), state)
            if payload is not None:
                rows = parse_financial_results(payload)
                count += _write(connection, "financial_results", rows,
                                ("symbol", "from_date", "to_date"),
                                ("period", "audited", "cumulative", "consolidated", "xbrl_link"))
            _pause()
    elif command == "fii-dii":
        payload = _request(session, lambda: session.get(API + "fiidiiTradeReact"), state)
        if payload is not None:
            rows = parse_fii_dii(payload)
            stamp = datetime.now().isoformat(sep=" ")
            for row in rows:
                row["created_at"] = stamp
            count = _write(connection, "fii_dii_daily", rows, ("date", "category", "segment"),
                            ("buy_value", "sell_value", "net_value"))
    elif command == "deals":
        for deal_type, filename in (("BULK", "bulk.csv"), ("BLOCK", "block.csv")):
            deal_filter = getattr(args, "deal_type", None)
            if deal_filter and deal_filter != deal_type:
                continue
            payload = _request(session, lambda f=filename: session.download(ARCHIVE + f), state)
            if payload is not None:
                rows = parse_deals(payload, deal_type)
                if connection is not None:
                    rows = [row for row in rows if connection.execute(
                        "SELECT 1 FROM companies WHERE symbol = ?", (row["symbol"],)).fetchone()]
                count += _write(connection, "bulk_block_deals", rows,
                                ("symbol", "date", "deal_type", "client_name", "transaction", "quantity", "price"), ())
            _pause()
    print(f"{command}: {count} rows")
    return count


def _parse_cli_date(value: str) -> date:
    for pattern in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    raise argparse.ArgumentTypeError("date must be YYYY-MM-DD or DD-MM-YYYY")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    commands = ("announcements", "board-meetings", "results", "fii-dii", "deals", "all")
    for command in commands:
        sub = subparsers.add_parser(command, help=f"load {command}")
        sub.add_argument("--dry-run", action="store_true", help="fetch and parse without writing")
        if command in {"announcements", "results", "all"}:
            sub.add_argument("--from", dest="from_date", help="start date YYYY-MM-DD or DD-MM-YYYY")
            sub.add_argument("--to", dest="to_date", help="end date YYYY-MM-DD or DD-MM-YYYY")
        if command in {"announcements", "all"}:
            sub.add_argument("--days", type=int, default=7)
        if command in {"results", "all"}:
            sub.add_argument("--period", action="append", choices=("Quarterly", "Annual"),
                             help="period to request (repeatable; default both)")
        if command == "deals":
            sub.add_argument("--deal-type", choices=("BULK", "BLOCK"))
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    connection = _open_db(args.dry_run)
    periods = args.period or ["Quarterly", "Annual"] if args.command in {"results", "all"} else None
    if periods is not None:
        args.period = periods
    commands = ["announcements", "board-meetings", "results", "fii-dii", "deals"] if args.command == "all" else [args.command]
    state = {"failures": 0}
    try:
        with NSESession() as session:
            for command in commands:
                run_one(command, args, session, connection, state)
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()
