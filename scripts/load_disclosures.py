"""Fetch and load NSE insider, SAST, and promoter pledge disclosures."""
from __future__ import annotations

import argparse
import logging
import random
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scrapers.disclosure_loaders import parse_insider, parse_sast, parse_shp_master, parse_shp_xbrl, upsert_rows
from src.session import NSESession

API = "https://www.nseindia.com/api/"
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "nse.db"
LOG = logging.getLogger("load_disclosures")


def _schema(connection: sqlite3.Connection | None) -> None:
    if connection is None:
        return
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS promoter_pledge (
            symbol TEXT NOT NULL,
            as_of DATE NOT NULL,
            quarter TEXT,
            promoter_pct NUMERIC,
            pledged_shares INTEGER,
            pledged_pct_of_total NUMERIC,
            pledged_pct_of_promoter NUMERIC,
            any_pledge INTEGER,
            source_url TEXT,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (symbol, as_of)
        );
        CREATE TABLE IF NOT EXISTS sast_disclosures (
            symbol TEXT NOT NULL,
            company TEXT,
            acquirer TEXT NOT NULL,
            sale_type TEXT,
            mode TEXT,
            shares_acquired INTEGER,
            shares_sold INTEGER,
            shares_after INTEGER,
            pct_acquired NUMERIC,
            pct_after NUMERIC,
            reg_type TEXT,
            promoter INTEGER,
            disclosed_at DATE NOT NULL,
            attachment TEXT,
            PRIMARY KEY (symbol, acquirer, disclosed_at)
        );
    """)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(promoter_pledge)")}
    if "total_shares" not in columns:
        connection.execute("ALTER TABLE promoter_pledge ADD COLUMN total_shares INTEGER")
    connection.commit()


def _open_db(dry_run: bool) -> sqlite3.Connection | None:
    if dry_run:
        return None
    connection = sqlite3.connect(DB_PATH, timeout=60)
    connection.execute("PRAGMA busy_timeout = 60000")
    connection.execute("PRAGMA foreign_keys = ON")
    _schema(connection)
    return connection


def _pause() -> None:
    time.sleep(random.uniform(1.5, 2.5))


def _request(action, state: dict[str, int]):
    try:
        result = action()
    except Exception as exc:
        state["failures"] += 1
        LOG.warning("NSE request failed (%d consecutive): %s", state["failures"], exc)
        if state["failures"] >= 8:
            raise RuntimeError("aborting after eight consecutive NSE request failures") from exc
        return None
    state["failures"] = 0
    return result


def _symbols(connection: sqlite3.Connection | None, args: argparse.Namespace) -> list[str]:
    if args.symbols:
        symbols = [value.strip().upper() for value in args.symbols.split(",") if value.strip()]
    elif connection is not None:
        symbols = [row[0] for row in connection.execute(
            "SELECT symbol FROM universes WHERE name = ? ORDER BY symbol", (args.universe,))]
    else:
        symbols = []
    return symbols[:args.limit] if args.limit else symbols


def run(command: str, args: argparse.Namespace, session: NSESession,
        connection: sqlite3.Connection | None, state: dict[str, int]) -> int:
    count = 0
    end = date.today()
    start = end - timedelta(days=args.days - 1)
    if command == "insider":
        symbols = _symbols(connection, args)
        for symbol in symbols:
            payload = _request(lambda: session.get(API + "corporates-pit", params={
                "index": "equities", "symbol": symbol,
                "from_date": start.strftime("%d-%m-%Y"), "to_date": end.strftime("%d-%m-%Y")}), state)
            if payload is not None:
                parsed = parse_insider(payload, symbol)
                count += len(parsed["insider_trading"])
                if connection is not None:
                    upsert_rows(connection, "insider_trading", parsed["insider_trading"],
                                ("symbol", "person_name", "transaction_type", "from_date"),
                                ("category", "securities_type", "no_of_shares", "value", "to_date", "broadcast_date", "created_at"))
                    upsert_rows(connection, "fd_insider_trading", parsed["fd_insider_trading"],
                                ("symbol", "date", "insider_name", "transaction", "quantity", "price"),
                                ("category", "post_holding"))
            _pause()
    elif command == "sast":
        cursor = start
        while cursor <= end:
            window_end = min(cursor + timedelta(days=2), end)
            payload = _request(lambda first=cursor, last=window_end: session.get(
                API + "corporate-sast-reg29", params={"index": "equities",
                "from_date": first.strftime("%d-%m-%Y"), "to_date": last.strftime("%d-%m-%Y")}), state)
            if payload is not None:
                rows = parse_sast(payload)
                count += len(rows)
                if connection is not None:
                    upsert_rows(connection, "sast_disclosures", rows,
                                ("symbol", "acquirer", "disclosed_at"),
                                ("company", "sale_type", "mode", "shares_acquired", "shares_sold", "shares_after",
                                 "pct_acquired", "pct_after", "reg_type", "promoter", "attachment"))
            cursor = window_end + timedelta(days=1)
            _pause()
    else:
        master = _request(lambda: session.get(API + "corporate-share-holdings-master", params={"index": "equities"}), state)
        if master is not None:
            filings = {row["symbol"]: row for row in parse_shp_master(master)}
            symbols = _symbols(connection, args) or (list(filings)[:args.limit] if args.limit else list(filings))
            for symbol in symbols:
                filing = filings.get(symbol)
                if not filing:
                    continue
                if connection is not None and not args.force:
                    exists = connection.execute("SELECT 1 FROM promoter_pledge WHERE symbol = ? AND as_of = ? AND total_shares IS NOT NULL",
                                                (symbol, filing["as_of"])).fetchone()
                    if exists:
                        continue
                url = filing["source_url"]
                if not url:
                    continue
                content = _request(lambda link=url: session.download(link), state)
                if content is not None:
                    facts = parse_shp_xbrl(content)
                    row = {"symbol": symbol, "as_of": filing["as_of"], "quarter": filing["quarter"],
                           "promoter_pct": facts["promoter_pct"] or filing["promoter_pct"],
                           "pledged_shares": facts["pledged_shares"],
                           "pledged_pct_of_total": facts["pledged_pct_of_total"],
                           "pledged_pct_of_promoter": facts["pledged_pct_of_promoter"],
                           "total_shares": facts["total_shares"],
                           "any_pledge": int(facts["any_pledge"]), "source_url": url,
                           "updated_at": datetime.now().isoformat(sep=" ")}
                    count += 1
                    if connection is not None:
                        upsert_rows(connection, "promoter_pledge", [row], ("symbol", "as_of"),
                                    ("quarter", "promoter_pct", "pledged_shares", "pledged_pct_of_total",
                                     "pledged_pct_of_promoter", "total_shares", "any_pledge", "source_url", "updated_at"))
                        connection.execute("UPDATE fd_shareholding SET promoter_pledge_pct = ? WHERE symbol = ? AND quarter = ?",
                                           (facts["pledged_pct_of_promoter"], symbol, filing["quarter"]))
                        connection.commit()
                _pause()
    print(f"{command}: {count} rows")
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("insider", "sast", "pledge"):
        sub = subs.add_parser(command, help=f"load {command} disclosures")
        sub.add_argument("--dry-run", action="store_true", help="fetch and parse without writing")
        sub.add_argument("--days", type=int, default=30 if command == "sast" else 365)
        sub.add_argument("--symbols", help="comma-separated symbol override")
        sub.add_argument("--limit", type=int)
        sub.add_argument("--universe", default="NIFTY_500")
        if command == "pledge":
            sub.add_argument("--force", action="store_true", help="refresh already loaded filings")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    connection = _open_db(args.dry_run)
    state = {"failures": 0}
    try:
        with NSESession() as session:
            run(args.command, args, session, connection, state)
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()
