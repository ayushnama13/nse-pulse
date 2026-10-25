"""Snapshot analytics math. Storage is delegated to db.py (SQLite)."""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta

from .repository import repo as db  # storage seam — swap backends in repository.py
from . import greeks
from .config import (
    IST,
    LOT_SIZES,
    SNAPSHOT_INTERVAL_SEC,
    SNAPSHOT_WINDOW_CLOSE,
    SNAPSHOT_WINDOW_OPEN,
    get_lot_size,
)

log = logging.getLogger("snapshots")


def is_within_snapshot_window(now: datetime | None = None) -> bool:
    """True iff the current IST time falls Mon–Fri inside the configured snapshot window."""
    n = (now or datetime.now(IST)).astimezone(IST)
    if n.weekday() >= 5:
        return False
    return SNAPSHOT_WINDOW_OPEN <= n.time() <= SNAPSHOT_WINDOW_CLOSE


def _safe_num(v, default=0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v, default=0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def _norm_expiry(s) -> str:
    return str(s or "").strip().upper().replace(" ", "")


def _row_from_rec(rec: dict) -> dict:
    strike = _safe_num(rec.get("strikePrice"))
    ce = rec.get("CE") or {}
    pe = rec.get("PE") or {}
    return {
        "strike": strike,
        "ceOI":  _safe_int(ce.get("openInterest")),
        "peOI":  _safe_int(pe.get("openInterest")),
        "ceChg": _safe_int(ce.get("changeinOpenInterest")),
        "peChg": _safe_int(pe.get("changeinOpenInterest")),
        "ceVol": _safe_int(ce.get("totalTradedVolume")),
        "peVol": _safe_int(pe.get("totalTradedVolume")),
        "ceLTP": _safe_num(ce.get("lastPrice")),
        "peLTP": _safe_num(pe.get("lastPrice")),
        "ceIV":  _safe_num(ce.get("impliedVolatility")),
        "peIV":  _safe_num(pe.get("impliedVolatility")),
    }


def _build_chain_rows(records_data: list[dict], current_expiry: str) -> tuple[list[dict], str]:
    """
    Filter records to a single expiry. Tolerates case/whitespace differences
    between `records.expiryDates` and `data[i].expiryDate`. If the requested
    expiry yields no rows but other expiries exist, fall back to the most
    populous expiry. Returns (rows, effective_expiry).
    """
    target = _norm_expiry(current_expiry)
    by_expiry: dict[str, list[dict]] = defaultdict(list)
    raw_label_for: dict[str, str] = {}
    for rec in records_data:
        # NSE option-chain-v3 uses the plural key `expiryDates` per record
        # (containing one string in DD-MMM-YYYY format). The old endpoint
        # used singular `expiryDate`. CE/PE sub-objects use yet another
        # format (DD-MM-YYYY numeric), so prefer the record-level key.
        e = rec.get("expiryDates") or rec.get("expiryDate")
        if not e:
            ce = rec.get("CE") or {}
            pe = rec.get("PE") or {}
            e = ce.get("expiryDate") or pe.get("expiryDate")
        if not e:
            continue
        k = _norm_expiry(e)
        by_expiry[k].append(rec)
        raw_label_for.setdefault(k, e)

    chosen_key = target if target in by_expiry else None
    if chosen_key is None and by_expiry:
        chosen_key = max(by_expiry, key=lambda k: len(by_expiry[k]))
        log.warning(
            f"[Snapshots] expiry '{current_expiry}' not found in data; "
            f"falling back to '{raw_label_for[chosen_key]}' "
            f"(available: {list(raw_label_for.values())[:6]})"
        )

    if chosen_key is None:
        return [], current_expiry

    rows = [_row_from_rec(r) for r in by_expiry[chosen_key]]
    rows.sort(key=lambda r: r["strike"])
    return rows, raw_label_for[chosen_key]


def _max_pain(chain: list[dict]) -> float:
    if not chain:
        return 0.0
    strikes = [r["strike"] for r in chain]
    best_strike = strikes[0]
    best_pain = float("inf")
    for s in strikes:
        pain = 0.0
        for r in chain:
            if s > r["strike"]:
                pain += r["ceOI"] * (s - r["strike"])
            if s < r["strike"]:
                pain += r["peOI"] * (r["strike"] - s)
        if pain < best_pain:
            best_pain = pain
            best_strike = s
    return best_strike


def _spot_from_records(raw: dict) -> float:
    rec = raw.get("records") or {}
    spot = rec.get("underlyingValue")
    if spot is not None:
        return _safe_num(spot)
    data = rec.get("data") or []
    for d in data:
        for side in ("CE", "PE"):
            if d.get(side) and d[side].get("underlyingValue"):
                return _safe_num(d[side]["underlyingValue"])
    return 0.0


def _gamma_exposure(
    chain: list[dict],
    spot: float,
    expiry_str: str | None = None,
) -> tuple[list[dict], float | None]:
    """Per-strike Gamma Exposure (GEX) and the cumulative-zero gamma-flip strike.

    Uses Black-Scholes Γ when `expiry_str` is provided (with per-strike NSE IV),
    and falls back to the legacy Gaussian γ-proxy when IV/expiry is unavailable
    (e.g. recompute against very old rows that pre-date this field).

    Sign convention: dealers are net SHORT what retail buys → CE OI flow is
    a negative dealer gamma contribution and PE OI flow is positive. We invert
    the convention from the legacy version to align with mainstream GEX charts
    (positive cumulative GEX = call wall = mean-reverting; negative = put wall
    = trending).
    """
    if not chain or not spot:
        return [], None

    use_bs = bool(expiry_str)
    T = greeks.time_to_expiry_years(expiry_str, datetime.now(IST)) if use_bs else 0.0

    # Legacy Gaussian proxy params (used when IV missing)
    strikes = [r["strike"] for r in chain]
    spread = max((max(strikes) - min(strikes)) / 4.0, spot * 0.02)

    out: list[dict] = []
    cum_list: list[tuple[float, float]] = []
    cum = 0.0
    for r in chain:
        ce_iv = (r.get("ceIV") or 0.0) / 100.0
        pe_iv = (r.get("peIV") or 0.0) / 100.0
        if use_bs and (ce_iv > 0 or pe_iv > 0):
            g_ce = greeks.bs_gamma(spot, r["strike"], T, ce_iv) if ce_iv > 0 else 0.0
            g_pe = greeks.bs_gamma(spot, r["strike"], T, pe_iv) if pe_iv > 0 else 0.0
        else:
            d = (r["strike"] - spot) / spread
            gproxy = math.exp(-0.5 * d * d)
            g_ce = g_pe = gproxy / 1e10  # scale-compat with legacy output

        # Per-side dollar gamma in ₹-billion-ish units (× spot²)
        ce_dgex = r["ceOI"] * g_ce * spot * spot
        pe_dgex = r["peOI"] * g_pe * spot * spot
        # Aggregate: CE-heavy → positive GEX (call wall), PE-heavy → negative.
        signed = ce_dgex - pe_dgex
        # Renormalize to keep numbers small for the UI
        scale = 1e7 if use_bs else 1.0
        out.append({
            "strike": r["strike"],
            "gex":   round(signed / scale, 3),
            "ceGex": round(ce_dgex / scale, 3),
            "peGex": round(-pe_dgex / scale, 3),
        })
        cum += signed / scale
        cum_list.append((r["strike"], cum))

    flip: float | None = None
    for i in range(1, len(cum_list)):
        sp, cp = cum_list[i-1]
        sc, cc = cum_list[i]
        if cp * cc < 0:
            denom = cc - cp
            t = -cp / denom if denom else 0.5
            flip = sp + t * (sc - sp)
            break
    if flip is None and cum_list:
        flip = min(cum_list, key=lambda x: abs(x[1]))[0]
    return out, flip


def _wpcr(chain: list[dict]) -> float:
    """Premium-weighted PCR — Σ(peOI · peLTP) / Σ(ceOI · ceLTP).

    Mirrors the client-side computation at public/index.html (kept there as a
    fallback for snapshots persisted before this column existed).
    """
    ce_val = sum(r["ceOI"] * r["ceLTP"] for r in chain)
    pe_val = sum(r["peOI"] * r["peLTP"] for r in chain)
    return round(pe_val / max(ce_val, 1), 4)


def compute_snapshot(symbol: str, raw: dict, requested_expiry: str | None = None) -> dict:
    rec = raw.get("records") or {}
    data = rec.get("data") or []
    expiries = rec.get("expiryDates") or []
    requested = requested_expiry or (expiries[0] if expiries else "")

    chain, current_expiry = _build_chain_rows(data, requested)
    if not chain:
        log.error(
            f"[Snapshots] empty chain for {symbol}: "
            f"records.data items={len(data)} expiryDates={expiries[:3]} "
            f"sample_keys={list(data[0].keys()) if data else []}"
        )
    spot = _spot_from_records(raw)

    total_ce = sum(r["ceOI"] for r in chain)
    total_pe = sum(r["peOI"] for r in chain)
    total_ce_vol = sum(r["ceVol"] for r in chain)
    total_pe_vol = sum(r["peVol"] for r in chain)
    pcr = total_pe / max(total_ce, 1)
    vol_pcr = total_pe_vol / max(total_ce_vol, 1)
    mp = _max_pain(chain)

    atm_strike = None
    atm_straddle = 0.0
    atm_ce_iv = 0.0
    atm_pe_iv = 0.0
    if chain and spot:
        atm_row = min(chain, key=lambda r: abs(r["strike"] - spot))
        atm_strike = atm_row["strike"]
        atm_straddle = atm_row["ceLTP"] + atm_row["peLTP"]
        atm_ce_iv = atm_row["ceIV"]
        atm_pe_iv = atm_row["peIV"]

    gex, gamma_flip = _gamma_exposure(chain, spot, current_expiry)
    wpcr = _wpcr(chain)

    now = datetime.now(IST)
    return {
        "time": now.strftime("%H:%M"),
        "timestamp": now.isoformat(),
        "symbol": symbol.upper(),
        "lotSize": get_lot_size(symbol),
        "spot": spot,
        "pcr": round(pcr, 4),
        "volPcr": round(vol_pcr, 4),
        "wpcr": wpcr,
        "maxPain": mp,
        "totalCEOI": total_ce,
        "totalPEOI": total_pe,
        "totalCEVol": total_ce_vol,
        "totalPEVol": total_pe_vol,
        "atmStrike": atm_strike,
        "atmStraddle": round(atm_straddle, 2),
        "atmCeIV": round(atm_ce_iv, 2),
        "atmPeIV": round(atm_pe_iv, 2),
        "gammaFlip": round(gamma_flip, 2) if gamma_flip is not None else None,
        "gex": gex,
        "expiries": expiries,
        "currentExpiry": current_expiry,
        "data": data,
        "chain": chain,
    }


def add_snapshot(
    symbol: str,
    raw: dict,
    requested_expiry: str | None = None,
    force: bool = False,
) -> dict:
    """Compute the snapshot from raw data and persist it.

    Two gates control persistence — `force=True` bypasses **both**:
    1. **Snapshot window** — Mon–Fri 09:00–15:30 IST. Outside this, automatic
       captures (passive `/api/option-chain` polls, scheduler ticks) do NOT
       persist; the computed snapshot is still returned for live display.
       Manual force-snapshots (the "Snapshot" button via `POST /api/snapshot`
       with `force=True`) persist regardless of time.
    2. **Throttle** — within the window, if the most recent stored snapshot
       is younger than `SNAPSHOT_INTERVAL_SEC`, skip persistence. Also
       bypassed by `force=True` (scheduler ticks, manual Snap button).
    """
    snap = compute_snapshot(symbol, raw, requested_expiry)

    # Gate 1: window cutoff — bypassed when caller explicitly forces.
    if not force and not is_within_snapshot_window():
        return snap

    # Gate 2: throttle (bypassable via force)
    persist = force
    if not persist:
        latest = db.latest_snapshot(symbol)
        if latest is None:
            persist = True
        else:
            try:
                last_ts = datetime.fromisoformat(latest["timestamp"])
                age = (datetime.now(IST) - last_ts).total_seconds()
                persist = age >= SNAPSHOT_INTERVAL_SEC
            except Exception:
                persist = True
    if persist:
        try:
            db.upsert_snapshot(snap)
        except Exception as e:
            log.error(f"[Snapshots] DB upsert failed for {symbol}: {e}")
    return snap


def _meta(snap: dict) -> dict:
    return {
        "time": snap["time"],
        "timestamp": snap["timestamp"],
        "symbol": snap["symbol"],
        "lotSize": snap.get("lotSize", get_lot_size(snap.get("symbol", ""))),
        "spot": snap["spot"],
        "pcr": snap["pcr"],
        "volPcr": snap.get("volPcr", 0),
        "wpcr": snap.get("wpcr", 0),
        "maxPain": snap["maxPain"],
        "totalCEOI": snap["totalCEOI"],
        "totalPEOI": snap["totalPEOI"],
        "atmStrike": snap.get("atmStrike"),
        "atmStraddle": snap.get("atmStraddle", 0),
        "currentExpiry": snap["currentExpiry"],
    }


def _bucket(symbol: str, limit: int = 500) -> list[dict]:
    """Pull snapshots from DB and back-fill lotSize (DB rows predating this field)."""
    rows = db.list_snapshots(symbol, limit=limit)
    lot = get_lot_size(symbol)
    for r in rows:
        r.setdefault("lotSize", lot)
    return rows


def get_snapshots(symbol: str, limit: int = 200) -> list[dict]:
    return [_meta(s) for s in _bucket(symbol, limit)]


def get_snapshot(symbol: str, idx: int) -> dict | None:
    bucket = _bucket(symbol, limit=2000)
    if 0 <= idx < len(bucket):
        return bucket[idx]
    return None


def get_snapshot_by_ts(symbol: str, timestamp: str) -> dict | None:
    """Look up a stored snapshot by its exact ISO timestamp."""
    bucket = _bucket(symbol, limit=4000)
    for s in bucket:
        if s["timestamp"] == timestamp:
            return s
    return None


def snapshot_counts() -> dict[str, int]:
    return db.snapshot_counts()


def _build_compare_payload(symbol: str, sa: dict, sb: dict) -> dict:
    by_strike_a = {r["strike"]: r for r in sa["chain"]}
    by_strike_b = {r["strike"]: r for r in sb["chain"]}
    all_strikes = sorted(set(by_strike_a) | set(by_strike_b))

    rows = []
    for s in all_strikes:
        ra = by_strike_a.get(s, {"ceOI": 0, "peOI": 0, "ceLTP": 0, "peLTP": 0})
        rb = by_strike_b.get(s, {"ceOI": 0, "peOI": 0, "ceLTP": 0, "peLTP": 0})
        rows.append({
            "strike": s,
            "ceOIA": ra["ceOI"], "ceOIB": rb["ceOI"],
            "peOIA": ra["peOI"], "peOIB": rb["peOI"],
            "ceOIDelta": rb["ceOI"] - ra["ceOI"],
            "peOIDelta": rb["peOI"] - ra["peOI"],
            "ceLTPA": ra.get("ceLTP", 0), "ceLTPB": rb.get("ceLTP", 0),
            "peLTPA": ra.get("peLTP", 0), "peLTPB": rb.get("peLTP", 0),
        })
    return {
        "symbol": symbol.upper(),
        "a": _meta(sa),
        "b": _meta(sb),
        "spotMove": round((sb.get("spot") or 0) - (sa.get("spot") or 0), 2),
        "pcrShift": round((sb.get("pcr") or 0) - (sa.get("pcr") or 0), 4),
        "maxPainShift": (sb.get("maxPain") or 0) - (sa.get("maxPain") or 0),
        "rows": rows,
    }


def compare_by_ts(symbol: str, ts_a: str, ts_b: str) -> dict:
    sa = get_snapshot_by_ts(symbol, ts_a)
    sb = get_snapshot_by_ts(symbol, ts_b)
    if sa is None:
        raise ValueError(f"snapshot not found: A={ts_a}")
    if sb is None:
        raise ValueError(f"snapshot not found: B={ts_b}")
    return _build_compare_payload(symbol, sa, sb)


def compare(symbol: str, a: int, b: int) -> dict:
    sa = get_snapshot(symbol, a)
    sb = get_snapshot(symbol, b)
    if sa is None or sb is None:
        raise IndexError("snapshot index out of range")
    return _build_compare_payload(symbol, sa, sb)


def get_oi_history(
    symbol: str,
    strikes: list[int] | None = None,
    top: int = 6,
    window_minutes: int | None = None,
) -> dict:
    """Time series of CE/PE OI for selected strikes across stored snapshots.
    If `strikes` is None, picks the top-N by total OI in the latest snapshot.
    If `window_minutes` is set, filters to snapshots within that window of the latest."""
    cap = 4000 if window_minutes else 200
    bucket = _bucket(symbol, limit=cap)
    if not bucket:
        return {"strikes": [], "series": []}

    if window_minutes:
        try:
            latest_ts = datetime.fromisoformat(bucket[-1]["timestamp"])
            cutoff = latest_ts - timedelta(minutes=window_minutes)
            bucket = [
                s for s in bucket
                if datetime.fromisoformat(s["timestamp"]) >= cutoff
            ]
        except Exception:
            pass

    if strikes is None:
        latest = bucket[-1]
        scored = sorted(
            ((r["strike"], r["ceOI"] + r["peOI"]) for r in latest["chain"]),
            key=lambda x: -x[1],
        )
        strikes = [s for s, _ in scored[:top]]

    series = []
    for snap in bucket:
        by_strike = {r["strike"]: r for r in snap["chain"]}
        point = {
            "time": snap["time"],
            "timestamp": snap["timestamp"],
            "spot": snap["spot"],
            "strikes": {},
        }
        for s in strikes:
            r = by_strike.get(s)
            point["strikes"][str(s)] = {
                "ceOI": r["ceOI"] if r else 0,
                "peOI": r["peOI"] if r else 0,
            }
        series.append(point)
    return {"strikes": strikes, "series": series}


def get_intraday_flow(symbol: str, limit: int = 200) -> dict:
    """Total CE/PE ΔOI per snapshot — the intraday cumulative shift since prior close."""
    bucket = _bucket(symbol, limit=limit)
    out = []
    for snap in bucket:
        ce_chg = sum((r.get("ceChg") or 0) for r in snap["chain"])
        pe_chg = sum((r.get("peChg") or 0) for r in snap["chain"])
        out.append({
            "time": snap["time"],
            "timestamp": snap["timestamp"],
            "spot": snap["spot"],
            "totalCeChg": ce_chg,
            "totalPeChg": pe_chg,
            "netChg": pe_chg - ce_chg,
        })
    return {"series": out}


def get_strike_detail(symbol: str, strike: float) -> dict:
    """For a single strike, returns LTP / OI / IV / ΔOI series across all stored snapshots."""
    bucket = _bucket(symbol, limit=200)
    series = []
    for snap in bucket:
        for r in snap["chain"]:
            if abs(r["strike"] - strike) < 0.5:
                series.append({
                    "time": snap["time"],
                    "timestamp": snap["timestamp"],
                    "spot": snap["spot"],
                    "ceOI":  r["ceOI"],  "peOI":  r["peOI"],
                    "ceLTP": r["ceLTP"], "peLTP": r["peLTP"],
                    "ceIV":  r["ceIV"],  "peIV":  r["peIV"],
                    "ceChg": r["ceChg"], "peChg": r["peChg"],
                })
                break
    return {"strike": strike, "series": series}


def get_oi_change(symbol: str, window_minutes: int) -> dict:
    """Per-strike CE/PE OI delta between the latest snapshot and the snapshot
    closest to `window_minutes` ago (within stored history)."""
    bucket = _bucket(symbol, limit=500)
    if len(bucket) < 2:
        return {"available": False, "rows": [], "summary": None, "snapshotCount": len(bucket)}

    latest = bucket[-1]
    try:
        latest_ts = datetime.fromisoformat(latest["timestamp"]).timestamp()
    except Exception:
        return {"available": False, "rows": [], "summary": None}

    target = latest_ts - window_minutes * 60
    candidate = bucket[0]
    for s in bucket[:-1]:
        try:
            ts = datetime.fromisoformat(s["timestamp"]).timestamp()
        except Exception:
            continue
        if ts <= target:
            candidate = s

    if candidate["timestamp"] == latest["timestamp"]:
        return {"available": False, "rows": [], "summary": None}

    by_a = {r["strike"]: r for r in candidate["chain"]}
    by_b = {r["strike"]: r for r in latest["chain"]}
    all_strikes = sorted(set(by_a) | set(by_b))

    rows = []
    tot_ce = 0
    tot_pe = 0
    for s in all_strikes:
        a = by_a.get(s, {"ceOI": 0, "peOI": 0})
        b = by_b.get(s, {"ceOI": 0, "peOI": 0})
        ce = b.get("ceOI", 0) - a.get("ceOI", 0)
        pe = b.get("peOI", 0) - a.get("peOI", 0)
        rows.append({"strike": s, "ceChg": ce, "peChg": pe})
        tot_ce += ce
        tot_pe += pe

    return {
        "available": True,
        "rows": rows,
        "summary": {
            "fromTime": candidate["time"],
            "toTime": latest["time"],
            "fromTimestamp": candidate["timestamp"],
            "toTimestamp": latest["timestamp"],
            "fromSpot": candidate["spot"],
            "toSpot": latest["spot"],
            "totalCeChange": tot_ce,
            "totalPeChange": tot_pe,
        },
    }


def get_daily_aggregate(symbol: str, days: int) -> dict:
    """One row per trading day = the LAST snapshot of that date.
    Useful for multi-day OI / PCR / spot trends."""
    bucket = _bucket(symbol, limit=3000)
    if not bucket:
        return {"days": []}

    by_date: dict[str, dict] = {}
    for s in bucket:
        date = s["timestamp"][:10]
        existing = by_date.get(date)
        if not existing or s["timestamp"] > existing["timestamp"]:
            by_date[date] = s

    sorted_dates = sorted(by_date.keys())[-days:]
    return {
        "days": [
            {
                "date": d,
                "spot": by_date[d]["spot"],
                "pcr": by_date[d]["pcr"],
                "volPcr": by_date[d].get("volPcr", 0),
                "wpcr": by_date[d].get("wpcr", 0),
                "totalCEOI": by_date[d]["totalCEOI"],
                "totalPEOI": by_date[d]["totalPEOI"],
                "maxPain": by_date[d]["maxPain"],
            }
            for d in sorted_dates
        ]
    }


def classify_regime(snap: dict) -> dict:
    """Multi-signal regime classifier (Python port of the JS classifyRegime).

    Single source of truth — the JS version in the frontend should call this
    via /api/option-chain payload OR fall back to its local copy. The two
    implementations must produce the same labels for the same inputs.

    Inputs needed on `snap`: pcr, volPcr, wpcr, spot, gammaFlip, chain[].peChg/.ceChg.
    """
    signals: list[str] = []
    pcr = snap.get("pcr") or 0
    vol_pcr = snap.get("volPcr") or 0
    wpcr = snap.get("wpcr") or 0
    spot = snap.get("spot") or 0
    flip = snap.get("gammaFlip")
    chain = snap.get("chain") or []

    if pcr > 1.2: signals.append("bull")
    elif 0 < pcr < 0.8: signals.append("bear")

    if vol_pcr > 1.2: signals.append("bull")
    elif 0 < vol_pcr < 0.8: signals.append("bear")

    if wpcr > 1.2: signals.append("bull")
    elif 0 < wpcr < 0.8: signals.append("bear")

    if flip and spot:
        signals.append("bull" if spot > flip else "bear")

    net_pe = sum(r.get("peChg") or 0 for r in chain)
    net_ce = sum(r.get("ceChg") or 0 for r in chain)
    if net_pe - net_ce > 100_000: signals.append("bull")
    elif net_ce - net_pe > 100_000: signals.append("bear")

    bulls = signals.count("bull")
    bears = signals.count("bear")
    total = len(signals) or 1
    if bulls / total >= 0.7: regime, cls = "Bullish", "bull"
    elif bears / total >= 0.7: regime, cls = "Bearish", "bear"
    elif abs(bulls - bears) <= 1: regime, cls = "Neutral / Mixed", "neutral"
    elif bulls > bears: regime, cls = "Lean Bullish", "warn"
    else: regime, cls = "Lean Bearish", "warn"
    return {"regime": regime, "cls": cls, "bulls": bulls, "bears": bears, "signals": signals}


def get_regime_calendar(symbol: str, days: int = 30) -> dict:
    """Per (date, intraday-bucket) regime label. Drives the heatmap.

    Buckets: hourly, 09:xx through 15:xx (covers the 09:00-15:30 session).
    For each (date, bucket), classify the LAST snapshot in that bucket.
    """
    bucket = _bucket(symbol, limit=10_000)
    if not bucket:
        return {"days": [], "buckets": []}

    cutoff = (datetime.now(IST) - timedelta(days=days)).date().isoformat()
    bucket = [s for s in bucket if s["timestamp"][:10] >= cutoff]

    bands = [(9, 10), (10, 11), (11, 12), (12, 13), (13, 14), (14, 15), (15, 16)]
    band_labels = ["09:xx", "10:xx", "11:xx", "12:xx", "13:xx", "14:xx", "15:xx"]

    by_date: dict[str, dict[int, dict]] = defaultdict(dict)
    for snap in bucket:
        try:
            hh = int(snap["timestamp"][11:13])
        except (ValueError, IndexError):
            continue
        for idx, (lo, hi) in enumerate(bands):
            if lo <= hh < hi:
                existing = by_date[snap["timestamp"][:10]].get(idx)
                if existing is None or snap["timestamp"] > existing["timestamp"]:
                    by_date[snap["timestamp"][:10]][idx] = snap
                break

    days_out: list[dict] = []
    for date in sorted(by_date):
        cells = []
        for idx, label in enumerate(band_labels):
            snap = by_date[date].get(idx)
            if not snap:
                cells.append({"bucket": label, "regime": None, "cls": "empty"})
                continue
            r = classify_regime(snap)
            cells.append({"bucket": label, "regime": r["regime"], "cls": r["cls"],
                          "bulls": r["bulls"], "bears": r["bears"]})
        days_out.append({"date": date, "cells": cells})

    return {"days": days_out, "buckets": band_labels}


def calendar_row(expiry_str: str, raw: dict) -> dict | None:
    """Compute one Calendar-tab row from one NSE response (which contains
    data for `expiry_str`). Returns None if the response has no rows for
    the requested expiry.

    Callers (the /api/calendar route) should fetch each expiry separately
    — NSE's option-chain endpoint only returns one expiry's `records.data`
    at a time, so iterating expiries within a single response would
    incorrectly attribute the same chain to every expiry."""
    spot = _spot_from_records(raw)
    rec = raw.get("records") or {}
    data = rec.get("data") or []
    chain, current_expiry = _build_chain_rows(data, expiry_str)
    if not chain:
        return None
    total_ce = sum(r["ceOI"] for r in chain)
    total_pe = sum(r["peOI"] for r in chain)
    pcr = total_pe / max(total_ce, 1)
    mp = _max_pain(chain)
    atm = min(chain, key=lambda r: abs(r["strike"] - spot)) if spot else chain[0]
    try:
        exp_dt = datetime.strptime(current_expiry, "%d-%b-%Y").replace(
            hour=15, minute=30, tzinfo=IST)
        dte = max((exp_dt - datetime.now(IST)).total_seconds() / 86400, 0)
    except ValueError:
        dte = 0
    return {
        "expiry":      current_expiry,
        "dte":         round(dte, 2),
        "atmStrike":   atm["strike"],
        "atmStraddle": round(atm["ceLTP"] + atm["peLTP"], 2),
        "atmCeIV":     round(atm["ceIV"], 2),
        "atmPeIV":     round(atm["peIV"], 2),
        "atmIv":       round((atm["ceIV"] + atm["peIV"]) / 2, 2),
        "pcr":         round(pcr, 4),
        "maxPain":     mp,
        "totalCEOI":   total_ce,
        "totalPEOI":   total_pe,
        "strikes":     len(chain),
    }


def list_expiries(raw: dict, max_expiries: int = 6) -> list[str]:
    """Top-N expiry labels from a current NSE option-chain response."""
    rec = raw.get("records") or {}
    return (rec.get("expiryDates") or [])[:max_expiries]


def get_iv_percentile(symbol: str, days: int = 30) -> dict:
    """Where does the most-recent ATM IV sit vs the trailing `days` of stored
    ATM IV samples? Pure-Python so it works without DuckDB installed.
    """
    bucket = _bucket(symbol, limit=4000)
    if not bucket:
        return {"available": False, "samples": 0}
    cutoff_date = (datetime.now(IST) - timedelta(days=days)).date().isoformat()
    series: list[float] = []
    for s in bucket:
        if s["timestamp"][:10] < cutoff_date:
            continue
        ce = s.get("atmCeIV") or 0.0
        pe = s.get("atmPeIV") or 0.0
        if ce <= 0 and pe <= 0:
            continue
        # Use straddle IV (avg of CE+PE) so single-sided dropouts don't dominate.
        n = (1 if ce > 0 else 0) + (1 if pe > 0 else 0)
        series.append((ce + pe) / n)
    if len(series) < 5:
        return {"available": False, "samples": len(series), "windowDays": days}
    current = series[-1]
    below = sum(1 for v in series if v < current)
    pct = round(100 * below / max(len(series) - 1, 1), 2)
    sorted_s = sorted(series)
    return {
        "available": True,
        "samples":   len(series),
        "current":   round(current, 2),
        "percentile": pct,
        "min":       round(sorted_s[0], 2),
        "max":       round(sorted_s[-1], 2),
        "median":    round(sorted_s[len(sorted_s) // 2], 2),
        "windowDays": days,
    }


def get_straddle_history(symbol: str) -> dict:
    """ATM straddle premium across all stored snapshots."""
    bucket = _bucket(symbol, limit=200)
    return {
        "series": [
            {
                "time": s["time"],
                "timestamp": s["timestamp"],
                "spot": s["spot"],
                "strike": s.get("atmStrike"),
                "straddle": s.get("atmStraddle", 0),
                "pcr": s.get("pcr", 0),
                "volPcr": s.get("volPcr", 0),
                "wpcr": s.get("wpcr", 0),
            }
            for s in bucket
        ]
    }
