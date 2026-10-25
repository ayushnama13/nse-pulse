"""
Phase 0 — Source Smoke Test
Confirms each upstream data source is reachable and serving expected schema
BEFORE any pipeline code is written. Web sources change without notice; this
file is the single source of truth for "is this still working today?".

Run:  python -m stock.tests.smoke_test
or:   python stock/tests/smoke_test.py

Output:
  - Per-source status: WORKING / DEGRADED / BROKEN
  - Actual URL hit, status code, response sample (≤ 500 chars)
  - Final summary table

Exit code:
  0  if >= 3 of 4 critical sources are WORKING (NSE list, NSE bhav, BSE, Screener)
  1  otherwise
yfinance is treated as informational (works/doesn't, doesn't gate exit).
"""
from __future__ import annotations

import io
import json
import sys
import time
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable

import requests
from bs4 import BeautifulSoup


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

TIMEOUT = 20  # seconds, per request
SAMPLE_LEN = 400  # chars of response sample to print
SLEEP_BETWEEN = 1.5  # polite gap between hits

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #

@dataclass
class CheckResult:
    name: str
    status: str  # WORKING | DEGRADED | BROKEN
    url: str = ""
    http_status: int | None = None
    detail: str = ""
    sample: str = ""
    extras: dict = field(default_factory=dict)

    def banner(self) -> str:
        color = {"WORKING": "\033[92m", "DEGRADED": "\033[93m", "BROKEN": "\033[91m"}.get(
            self.status, ""
        )
        reset = "\033[0m"
        head = f"{color}[{self.status}]{reset} {self.name}"
        body = []
        if self.url:
            body.append(f"  url:    {self.url}")
        if self.http_status is not None:
            body.append(f"  http:   {self.http_status}")
        if self.detail:
            body.append(f"  detail: {self.detail}")
        if self.sample:
            short = self.sample.strip().replace("\n", " ")[:SAMPLE_LEN]
            body.append(f"  sample: {short}")
        for k, v in self.extras.items():
            body.append(f"  {k}: {v}")
        return head + "\n" + "\n".join(body)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def nse_session() -> requests.Session:
    """NSE blocks default UAs; warm up cookies on the homepage first."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    try:
        s.get("https://www.nseindia.com/", timeout=TIMEOUT)
        time.sleep(0.8)
    except requests.RequestException:
        pass
    return s


def bse_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.bseindia.com/",
        "Origin": "https://www.bseindia.com",
        "Connection": "keep-alive",
    })
    return s


def last_trading_day(today: date | None = None) -> date:
    """Walk back from today until we hit Mon-Fri (ignoring holidays)."""
    d = today or date.today()
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d -= timedelta(days=1)
    # If today is a weekday but the run is early in the day / before publish,
    # fall back one extra day; bhav typically published ~19:00 IST.
    return d


# --------------------------------------------------------------------------- #
# 1) yfinance
# --------------------------------------------------------------------------- #

def check_yfinance() -> CheckResult:
    name = "yfinance (RELIANCE.NS .info)"
    try:
        import yfinance as yf
    except ImportError as e:
        return CheckResult(name, "BROKEN", detail=f"yfinance not installed: {e}")

    try:
        t = yf.Ticker("RELIANCE.NS")
        info = t.info or {}
    except Exception as e:
        return CheckResult(name, "BROKEN", detail=f"Ticker.info raised: {type(e).__name__}: {e}")

    url = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/RELIANCE.NS"
    if not isinstance(info, dict) or not info:
        return CheckResult(name, "BROKEN", url=url, detail="empty .info dict")

    pe = info.get("trailingPE")
    mcap = info.get("marketCap")
    sample_keys = sorted(list(info.keys()))[:8]
    sample = (
        f"trailingPE={pe} marketCap={mcap} sector={info.get('sector')} "
        f"keys[:8]={sample_keys}"
    )

    if pe is None:
        return CheckResult(
            name, "DEGRADED", url=url,
            detail="trailingPE is null — yfinance Indian fundamentals patchy",
            sample=sample, extras={"keys_total": len(info)},
        )
    return CheckResult(
        name, "WORKING", url=url, http_status=200, sample=sample,
        extras={"keys_total": len(info)},
    )


# --------------------------------------------------------------------------- #
# 2) NSE equity list
# --------------------------------------------------------------------------- #

def check_nse_stock_list() -> CheckResult:
    name = "NSE equity list (EQUITY_L.csv)"
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    s = nse_session()
    try:
        r = s.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        return CheckResult(name, "BROKEN", url=url, detail=f"{type(e).__name__}: {e}")

    if r.status_code != 200:
        return CheckResult(name, "BROKEN", url=url, http_status=r.status_code,
                            detail="non-200")
    text = r.text
    lines = text.splitlines()
    if len(lines) < 2 or "SYMBOL" not in lines[0].upper():
        return CheckResult(name, "BROKEN", url=url, http_status=200,
                            detail="header missing SYMBOL", sample=text[:SAMPLE_LEN])
    rows = len(lines) - 1
    status = "WORKING" if rows >= 1500 else "DEGRADED"
    return CheckResult(
        name, status, url=url, http_status=200,
        detail=f"{rows} symbols",
        sample=lines[0] + " | " + (lines[1] if len(lines) > 1 else ""),
        extras={"rows": rows},
    )


# --------------------------------------------------------------------------- #
# 3) NSE bhav copy — try multiple URL formats
# --------------------------------------------------------------------------- #

def check_nse_bhav() -> CheckResult:
    """
    NSE has migrated bhav copy URLs multiple times. Probe known formats from
    newest to oldest, walking back up to 7 days to skip holidays.
    """
    name = "NSE bhav copy (latest)"
    s = nse_session()

    today = last_trading_day()
    candidates: list[tuple[str, str]] = []  # (label, url)
    for offset in range(0, 7):
        d = today - timedelta(days=offset)
        if d.weekday() >= 5:
            continue
        ymd = d.strftime("%Y%m%d")
        ddmmyyyy = d.strftime("%d%m%Y")
        ddmmm = d.strftime("%d%b%Y").upper()  # e.g. 08MAY2026
        mon = d.strftime("%b").upper()
        yyyy = d.strftime("%Y")

        # 2024+ format (UDIFF / new bhav copy)
        candidates.append((
            "new-udiff",
            f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip",
        ))
        # sec_bhavdata_full (also 2024+)
        candidates.append((
            "sec_bhavdata_full",
            f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{ddmmyyyy}.csv",
        ))
        # legacy archives path (may still work)
        candidates.append((
            "legacy-archives",
            f"https://archives.nseindia.com/content/historical/EQUITIES/{yyyy}/{mon}/cm{ddmmm}bhav.csv.zip",
        ))

    last_err: dict | None = None
    for label, url in candidates:
        try:
            r = s.get(url, timeout=TIMEOUT, headers={"Referer": "https://www.nseindia.com/"})
        except requests.RequestException as e:
            last_err = {"label": label, "url": url, "err": f"{type(e).__name__}: {e}"}
            continue
        if r.status_code != 200 or not r.content:
            last_err = {"label": label, "url": url, "err": f"http {r.status_code}, {len(r.content)}b"}
            time.sleep(0.4)
            continue

        # Parse: zip or plain csv
        try:
            if url.endswith(".zip"):
                z = zipfile.ZipFile(io.BytesIO(r.content))
                inner = z.namelist()[0]
                csv_bytes = z.read(inner)
            else:
                csv_bytes = r.content
            head = csv_bytes[:4096].decode("utf-8", errors="replace")
            lines = head.splitlines()
            if len(lines) < 2:
                last_err = {"label": label, "url": url, "err": "fewer than 2 lines"}
                continue
            header = lines[0].upper()
            ok_tokens = ("SYMBOL", "SERIES", "OPEN", "CLOSE")
            hits = sum(1 for tok in ok_tokens if tok in header)
            if hits < 2:
                last_err = {"label": label, "url": url, "err": f"header unfamiliar: {lines[0][:160]}"}
                continue
            return CheckResult(
                name, "WORKING", url=url, http_status=200,
                detail=f"format={label}",
                sample=lines[0] + " | " + lines[1],
                extras={"first_line_len": len(lines[0])},
            )
        except Exception as e:
            last_err = {"label": label, "url": url, "err": f"parse {type(e).__name__}: {e}"}
            continue

    return CheckResult(
        name, "BROKEN",
        url=(last_err or {}).get("url", ""),
        detail=f"all candidate URLs failed; last={last_err}",
    )


# --------------------------------------------------------------------------- #
# 4) BSE bulk deals
# --------------------------------------------------------------------------- #

def check_bse_bulk_deals() -> CheckResult:
    """
    BSE bulk-deals API. Tries the ddmmyyyy format used by the BSE site widget.
    """
    name = "BSE bulk deals API"
    s = bse_session()
    d = last_trading_day()
    last_err: dict | None = None

    for offset in range(0, 7):
        dt = d - timedelta(days=offset)
        if dt.weekday() >= 5:
            continue
        ddmmyyyy = dt.strftime("%d/%m/%Y")
        ymd = dt.strftime("%Y%m%d")

        candidates = [
            (
                "BulkDeals/w",
                f"https://api.bseindia.com/BseIndiaAPI/api/BulkDeals/w?strDate={ymd}",
            ),
            (
                "DDR-strType-BU",
                f"https://api.bseindia.com/BseIndiaAPI/api/DDR/w?strScrip=&strSDate={ddmmyyyy}&strEDate={ddmmyyyy}&strType=B&strDeals=BU",
            ),
            (
                "BlockDeals/w",
                f"https://api.bseindia.com/BseIndiaAPI/api/BlockDeals/w?strDate={ymd}",
            ),
        ]

        for label, url in candidates:
            try:
                r = s.get(url, timeout=TIMEOUT)
            except requests.RequestException as e:
                last_err = {"label": label, "url": url, "err": f"{type(e).__name__}: {e}"}
                continue

            if r.status_code != 200:
                last_err = {"label": label, "url": url, "err": f"http {r.status_code}"}
                continue

            try:
                data = r.json()
            except ValueError as e:
                last_err = {"label": label, "url": url, "err": f"not json: {e}; body[:200]={r.text[:200]}"}
                continue

            # Schemas seen: list[dict], dict with "Table"/"Data"/"d", or {"Bulkdeals":[...]}
            rows = None
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict):
                for key in ("Table", "Data", "Bulkdeals", "d", "Records"):
                    if isinstance(data.get(key), list):
                        rows = data[key]
                        break

            if rows is None:
                # JSON parsed but unrecognized shape — treat as DEGRADED, not BROKEN
                last_err = {"label": label, "url": url, "err": f"unknown shape keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"}
                continue

            sample_row = rows[0] if rows else {}
            sample = json.dumps(sample_row)[:SAMPLE_LEN] if sample_row else "(empty list — possibly no deals that day)"
            status = "WORKING" if rows else "DEGRADED"
            return CheckResult(
                name, status, url=url, http_status=200,
                detail=f"format={label}, n_rows={len(rows)}",
                sample=sample,
                extras={"date_tried": ddmmyyyy, "rows": len(rows)},
            )
            time.sleep(0.4)

    return CheckResult(
        name, "BROKEN",
        url=(last_err or {}).get("url", ""),
        detail=f"all BSE candidates failed; last={last_err}",
    )


# --------------------------------------------------------------------------- #
# 5) Screener.in
# --------------------------------------------------------------------------- #

def check_screener() -> CheckResult:
    name = "Screener.in (RELIANCE consolidated)"
    url = "https://www.screener.in/company/RELIANCE/consolidated/"
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        r = s.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        return CheckResult(name, "BROKEN", url=url, detail=f"{type(e).__name__}: {e}")

    if r.status_code == 429:
        return CheckResult(name, "DEGRADED", url=url, http_status=429,
                            detail="rate-limited at smoke time; honor backoff in pipeline")
    if r.status_code != 200:
        return CheckResult(name, "BROKEN", url=url, http_status=r.status_code, detail="non-200")

    html = r.text
    soup = BeautifulSoup(html, "lxml")
    expected_ids = ["profit-loss", "balance-sheet", "cash-flow", "ratios", "quarters", "shareholding"]
    found = {sid: bool(soup.find(id=sid)) for sid in expected_ids}
    missing = [k for k, v in found.items() if not v]

    sample = " ".join(f"{k}={'Y' if v else 'N'}" for k, v in found.items())
    if not missing:
        return CheckResult(name, "WORKING", url=url, http_status=200, sample=sample)
    if {"profit-loss", "balance-sheet", "cash-flow"}.issubset(set(found) - set(missing)):
        return CheckResult(
            name, "DEGRADED", url=url, http_status=200,
            detail=f"core sections present, optional missing: {missing}", sample=sample,
        )
    return CheckResult(
        name, "BROKEN", url=url, http_status=200,
        detail=f"core sections missing: {missing}", sample=sample,
    )


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

CHECKS: list[tuple[str, Callable[[], CheckResult], bool]] = [
    # (label, fn, is_critical)
    ("yfinance", check_yfinance, False),
    ("nse_stock_list", check_nse_stock_list, True),
    ("nse_bhav", check_nse_bhav, True),
    ("bse_bulk_deals", check_bse_bulk_deals, True),
    ("screener", check_screener, True),
]


def main() -> int:
    print("=" * 72)
    print(f"PHASE 0 — SOURCE SMOKE TEST   {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 72)

    results: list[tuple[str, CheckResult, bool]] = []
    for label, fn, critical in CHECKS:
        print(f"\n>>> {label}")
        try:
            res = fn()
        except Exception as e:
            res = CheckResult(label, "BROKEN", detail=f"smoke test crashed: {type(e).__name__}: {e}")
        print(res.banner())
        results.append((label, res, critical))
        time.sleep(SLEEP_BETWEEN)

    # Summary
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    for label, res, critical in results:
        tag = "[CRIT]" if critical else "[INFO]"
        print(f"  {tag} {label:24s} {res.status}")

    crit_working = sum(1 for _, r, c in results if c and r.status == "WORKING")
    crit_total = sum(1 for _, _, c in results if c)
    print(f"\nCritical sources: {crit_working}/{crit_total} WORKING")

    if crit_working >= 3:
        print("PASS — proceed to Phase 1 (foundation).")
        return 0
    print("FAIL — fix sources or document in SOURCES_STATUS.md before Phase 1.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
