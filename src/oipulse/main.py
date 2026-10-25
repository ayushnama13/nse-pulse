"""OI Pulse FastAPI application."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time as _time
from contextlib import asynccontextmanager
from datetime import datetime
from threading import Lock

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .repository import repo as db  # storage seam — swap backends in repository.py
from . import fetcher
from . import scheduler
from . import snapshots
from .config import (
    BASIC_AUTH_PASS,
    BASIC_AUTH_USER,
    CACHE_TTL_SEC,
    DB_PATH,
    DEBUG_ENABLED,
    INDEX_SYMBOLS,
    MACRO_TTL_SEC,
    NSE_MAX_CONCURRENCY,
    VERSION,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("main")

_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = Lock()

# ── Lightweight Prometheus-format metrics (no extra dependency) ───────────
_metrics_lock = Lock()
_METRICS = {
    "oipulse_fetch_total": 0,
    "oipulse_fetch_errors_total": 0,
    "oipulse_cache_hits_total": 0,
    "oipulse_sse_messages_total": 0,
}
_METRICS_HIST: dict[str, float] = {"oipulse_fetch_duration_seconds_sum": 0.0}
_METRICS_HIST_COUNT = {"oipulse_fetch_duration_seconds_count": 0}


def _metric_inc(name: str, n: int = 1) -> None:
    with _metrics_lock:
        _METRICS[name] = _METRICS.get(name, 0) + n


def _metric_obs(name: str, duration: float) -> None:
    with _metrics_lock:
        _METRICS_HIST[f"{name}_sum"] = _METRICS_HIST.get(f"{name}_sum", 0.0) + duration
        _METRICS_HIST_COUNT[f"{name}_count"] = _METRICS_HIST_COUNT.get(f"{name}_count", 0) + 1

# Hard ceiling on in-flight NSE calls — protects against burst-fetch storms.
_nse_sem: asyncio.Semaphore | None = None


def _ensure_sem() -> asyncio.Semaphore:
    global _nse_sem
    if _nse_sem is None:
        _nse_sem = asyncio.Semaphore(NSE_MAX_CONCURRENCY)
    return _nse_sem


async def _nse_fetch_option_chain(sym: str, expiry_dt):
    loop = asyncio.get_running_loop()
    t0 = _time.time()
    async with _ensure_sem():
        try:
            result = await loop.run_in_executor(None, fetcher.fetch_option_chain, sym, expiry_dt)
            _metric_inc("oipulse_fetch_total")
            return result
        except Exception:
            _metric_inc("oipulse_fetch_errors_total")
            raise
        finally:
            _metric_obs("oipulse_fetch_duration_seconds", _time.time() - t0)


# ── SSE broadcast plumbing ─────────────────────────────────────────────────
_subscribers: dict[str, set[asyncio.Queue]] = {}
_sub_lock = Lock()


def _broadcast(symbol: str, snap: dict) -> None:
    """Push a snapshot to every SSE subscriber for `symbol`. Drops slow clients."""
    with _sub_lock:
        queues = list(_subscribers.get(symbol, ()))
    if not queues:
        return
    # Strip the big `data` blob — clients have `chain` already.
    payload = {k: v for k, v in snap.items() if k != "data"}
    delivered = 0
    for q in queues:
        try:
            q.put_nowait(payload)
            delivered += 1
        except asyncio.QueueFull:
            pass  # slow consumer: drop
    if delivered:
        _metric_inc("oipulse_sse_messages_total", delivered)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    fetcher.init()
    _ensure_sem()
    scheduler.set_broadcaster(_broadcast)
    task = asyncio.create_task(scheduler.snapshot_loop())
    log.info(f"[Main] startup complete — version={VERSION['version']} sha={VERSION['sha']}")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        fetcher.shutdown()
        db.shutdown()
        log.info("[Main] shutdown complete")


# ── HTTP basic-auth shim (no-op when env vars unset) ───────────────────────
def _basic_ok(auth_header: str | None) -> bool:
    """Validate an Authorization: Basic header against the env-configured creds.
    True when auth is disabled. Used by the static-files middleware and the
    WebSocket route."""
    if not BASIC_AUTH_USER:
        return True
    if not auth_header or not auth_header.lower().startswith("basic "):
        return False
    try:
        import base64

        raw = base64.b64decode(auth_header.split(" ", 1)[1]).decode()
        user, _, pwd = raw.partition(":")
    except Exception:  # noqa: BLE001
        return False
    return secrets.compare_digest(user, BASIC_AUTH_USER) and secrets.compare_digest(
        pwd, BASIC_AUTH_PASS or ""
    )


app = FastAPI(
    lifespan=lifespan,
    title="OI Pulse",
    version=VERSION["version"],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _static_auth_guard(request: Request, call_next):
    """Single auth checkpoint for all HTTP requests (API + static). An
    app-level `Depends(auth_dep)` also broke the /ws/stream route (HTTPBasic
    can't resolve against a WebSocket scope), so auth is enforced only here
    and, for WS, via the manual `_basic_ok` check in ws_stream."""
    if BASIC_AUTH_USER and not _basic_ok(request.headers.get("authorization")):
        return PlainTextResponse(
            "Unauthorized",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="oipulse"'},
        )
    return await call_next(request)


def _validate_symbol(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if not s:
        raise HTTPException(status_code=400, detail={"error": "symbol required"})
    return s


def _parse_expiry(expiry: str | None) -> datetime | None:
    if not expiry:
        return None
    try:
        return datetime.strptime(expiry, "%d-%b-%Y")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "expiry must be DD-MMM-YYYY (e.g. 10-Apr-2026)"},
        )


def _cache_key(symbol: str, expiry: str | None) -> str:
    return f"{symbol.upper()}|{expiry or ''}"


@app.get("/api/option-chain")
async def option_chain(
    symbol: str = Query(...),
    expiry: str | None = Query(None),
):
    sym = _validate_symbol(symbol)
    expiry_dt = _parse_expiry(expiry)
    key = _cache_key(sym, expiry)

    now = _time.time()
    with _cache_lock:
        cached = _cache.get(key)
    if cached and (now - cached[0]) < CACHE_TTL_SEC:
        _metric_inc("oipulse_cache_hits_total")
        return cached[1]

    try:
        raw = await _nse_fetch_option_chain(sym, expiry_dt)
        snap = snapshots.add_snapshot(sym, raw, expiry)
        scheduler.LAST_FETCH[sym] = snap["timestamp"]
        payload = {**snap, "stale": False}
        with _cache_lock:
            _cache[key] = (now, payload)
        # If we persisted (window+throttle passed) the row, fan out to SSE.
        _broadcast(sym, snap)
        return payload
    except Exception as e:
        log.error(f"[Main] /api/option-chain failed for {sym}: {e}")
        if cached:
            stale_payload = {**cached[1], "stale": True, "error": str(e)}
            return stale_payload
        raise HTTPException(
            status_code=502,
            detail={"error": f"NSE fetch failed: {e}"},
        )


@app.get("/api/snapshots")
async def list_snapshots(symbol: str = Query(...)):
    sym = _validate_symbol(symbol)
    return {"symbol": sym, "snapshots": snapshots.get_snapshots(sym)}


@app.get("/api/snapshot/{idx}")
async def get_snapshot(idx: int, symbol: str = Query(...)):
    sym = _validate_symbol(symbol)
    snap = snapshots.get_snapshot(sym, idx)
    if snap is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "snapshot index out of range"},
        )
    return snap


class SnapshotIn(BaseModel):
    symbol: str
    expiry: str | None = None


@app.post("/api/snapshot")
async def force_snapshot(body: SnapshotIn):
    sym = _validate_symbol(body.symbol)
    expiry_dt = _parse_expiry(body.expiry)
    try:
        raw = await _nse_fetch_option_chain(sym, expiry_dt)
        snap = snapshots.add_snapshot(sym, raw, body.expiry, force=True)
        scheduler.LAST_FETCH[sym] = snap["timestamp"]
        with _cache_lock:
            _cache[_cache_key(sym, body.expiry)] = (_time.time(), {**snap, "stale": False})
        _broadcast(sym, snap)
        return snap
    except Exception as e:
        log.error(f"[Main] POST /api/snapshot failed for {sym}: {e}")
        raise HTTPException(status_code=502, detail={"error": f"NSE fetch failed: {e}"})


@app.get("/api/compare")
async def compare(
    symbol: str = Query(...),
    a: int | None = Query(None),
    b: int | None = Query(None),
    aTs: str | None = Query(None),
    bTs: str | None = Query(None),
):
    sym = _validate_symbol(symbol)
    if aTs and bTs:
        try:
            return snapshots.compare_by_ts(sym, aTs, bTs)
        except ValueError as e:
            raise HTTPException(status_code=404, detail={"error": str(e)})
    if a is not None and b is not None:
        try:
            return snapshots.compare(sym, a, b)
        except IndexError as e:
            raise HTTPException(status_code=404, detail={"error": str(e)})
    raise HTTPException(status_code=400, detail={"error": "provide either a&b (indices) or aTs&bTs (timestamps)"})


@app.get("/api/oi-history")
async def oi_history(
    symbol: str = Query(...),
    strikes: str | None = Query(None, description="comma-separated strike ints"),
    top: int = Query(6, ge=1, le=12),
    windowMin: int | None = Query(None, ge=1, le=43200),
):
    sym = _validate_symbol(symbol)
    sl = None
    if strikes:
        try:
            sl = [int(x) for x in strikes.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(400, {"error": "strikes must be comma-separated integers"})
    return snapshots.get_oi_history(sym, sl, top, windowMin)


@app.get("/api/straddle-history")
async def straddle_history(symbol: str = Query(...)):
    sym = _validate_symbol(symbol)
    return snapshots.get_straddle_history(sym)


@app.get("/api/oi-change")
async def oi_change(
    symbol: str = Query(...),
    windowMin: int = Query(120, ge=1, le=1440),
):
    sym = _validate_symbol(symbol)
    return snapshots.get_oi_change(sym, windowMin)


@app.get("/api/intraday-flow")
async def intraday_flow(symbol: str = Query(...), limit: int = Query(200, ge=1, le=500)):
    sym = _validate_symbol(symbol)
    return snapshots.get_intraday_flow(sym, limit)


@app.get("/api/strike-detail")
async def strike_detail(symbol: str = Query(...), strike: float = Query(...)):
    sym = _validate_symbol(symbol)
    return snapshots.get_strike_detail(sym, strike)


@app.get("/api/daily-aggregate")
async def daily_aggregate(
    symbol: str = Query(...),
    days: int = Query(30, ge=1, le=365),
):
    sym = _validate_symbol(symbol)
    return snapshots.get_daily_aggregate(sym, days)


_macro_cache: dict[str, tuple[float, dict]] = {}


def _macro_get(key: str):
    now = _time.time()
    c = _macro_cache.get(key)
    if c and (now - c[0]) < MACRO_TTL_SEC:
        return c[1]
    return None


def _macro_put(key: str, payload: dict):
    _macro_cache[key] = (_time.time(), payload)


async def _macro_call(name: str, fn, single_value: bool = False):
    """Shared body for the macro endpoints — handles cache, capability gaps
    (the modern `nse` library removed FII/DII and Participant-OI) and the
    transient-vs-permanent distinction (503 for missing capability, 502 for
    network/parse errors)."""
    cached = _macro_get(name)
    if cached:
        return cached
    loop = asyncio.get_running_loop()
    try:
        async with _ensure_sem():
            data = await loop.run_in_executor(None, fn)
        payload = {"data": data} if single_value else \
                  {"data": data if isinstance(data, list) else [data]}
        _macro_put(name, payload)
        return payload
    except fetcher.MacroUnavailable as e:
        log.warning(f"[Main] /api/{name} unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail={"error": str(e), "available": False, "endpoint": name},
        )
    except Exception as e:
        log.error(f"[Main] /api/{name} failed: {e}")
        raise HTTPException(status_code=502, detail={"error": str(e)})


@app.get("/api/vix")
async def vix():
    return await _macro_call("vix", fetcher.fetch_vix, single_value=True)


@app.get("/api/fii-dii")
async def fii_dii():
    return await _macro_call("fiiDii", fetcher.fetch_fii_dii)


@app.get("/api/participant-oi")
async def participant_oi():
    return await _macro_call("participantOi", fetcher.fetch_participant_oi)


@app.get("/api/multi")
async def multi(symbols: str = Query("NIFTY,BANKNIFTY,FINNIFTY")):
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        raise HTTPException(status_code=400, detail={"error": "no symbols"})

    async def fetch_one(sym: str) -> dict:
        key = _cache_key(sym, None)
        now = _time.time()
        with _cache_lock:
            cached = _cache.get(key)
        if cached and (now - cached[0]) < CACHE_TTL_SEC:
            snap = cached[1]
            return {k: v for k, v in snap.items() if k not in ("data",)}
        try:
            raw_resp = await _nse_fetch_option_chain(sym, None)
            snap = snapshots.add_snapshot(sym, raw_resp)
            scheduler.LAST_FETCH[sym] = snap["timestamp"]
            payload = {**snap, "stale": False}
            with _cache_lock:
                _cache[key] = (_time.time(), payload)
            _broadcast(sym, snap)
            return {k: v for k, v in payload.items() if k not in ("data",)}
        except Exception as e:
            log.error(f"[Main] /api/multi {sym} failed: {e}")
            return {"symbol": sym, "ok": False, "error": str(e)}

    results = await asyncio.gather(*[fetch_one(s) for s in sym_list])
    return {"results": results}


# ── SSE stream ─────────────────────────────────────────────────────────────
@app.get("/api/stream")
async def stream(symbol: str = Query(...), request: Request = None):
    """Server-Sent Events stream — one message per persisted snapshot.

    Clients should EventSource('/api/stream?symbol=NIFTY') and consume
    `data:` frames. A `: keepalive` comment frame goes out every 15s so
    intermediaries (nginx, Cloudflare) don't drop the connection.
    """
    sym = _validate_symbol(symbol)
    q: asyncio.Queue = asyncio.Queue(maxsize=10)
    with _sub_lock:
        _subscribers.setdefault(sym, set()).add(q)

    async def gen():
        try:
            # Initial sync: send latest persisted snapshot so the client
            # never sees a blank screen while waiting for the next push.
            latest = db.latest_snapshot(sym)
            if latest:
                yield f"data: {json.dumps(latest, default=str)}\n\n"
            while True:
                if request is not None and await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(payload, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            with _sub_lock:
                subs = _subscribers.get(sym)
                if subs:
                    subs.discard(q)
                    if not subs:
                        _subscribers.pop(sym, None)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # tell nginx not to buffer
            "Connection": "keep-alive",
        },
    )


@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    """WebSocket twin of /api/stream. Same pub/sub (`_subscribers`/`_broadcast`),
    bidirectional: the client sends `{"symbol": "NIFTY"}` to (re)subscribe.
    Frontend prefers this; SSE remains the fallback. Additive — does not change
    the SSE path."""
    # Basic-auth (when enabled). Browsers can't attach headers to a WebSocket
    # handshake, so credentialed deployments typically land on the SSE fallback
    # (which browsers DO authenticate); non-browser clients can send the header.
    if not _basic_ok(websocket.headers.get("authorization")):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    sym = (websocket.query_params.get("symbol") or "NIFTY").strip().upper()
    q: asyncio.Queue = asyncio.Queue(maxsize=10)

    def _subscribe(s: str) -> None:
        with _sub_lock:
            _subscribers.setdefault(s, set()).add(q)

    def _unsubscribe(s: str) -> None:
        with _sub_lock:
            subs = _subscribers.get(s)
            if subs:
                subs.discard(q)
                if not subs:
                    _subscribers.pop(s, None)

    _subscribe(sym)
    try:
        latest = db.latest_snapshot(sym)
        if latest:
            await websocket.send_json({k: v for k, v in latest.items() if k != "data"})

        async def pump() -> None:
            while True:
                payload = await q.get()
                await websocket.send_json(payload)

        async def recv() -> None:
            nonlocal sym
            while True:
                msg = await websocket.receive_json()
                new_sym = (msg.get("symbol") or sym).strip().upper()
                if new_sym != sym:
                    _unsubscribe(sym)
                    sym = new_sym
                    _subscribe(sym)
                    snap = db.latest_snapshot(sym)
                    if snap:
                        await websocket.send_json({k: v for k, v in snap.items() if k != "data"})

        pump_task = asyncio.create_task(pump())
        recv_task = asyncio.create_task(recv())
        _, pending = await asyncio.wait({pump_task, recv_task}, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001
        log.info(f"[Main] /ws/stream closed: {e}")
    finally:
        _unsubscribe(sym)


@app.get("/api/version")
async def version():
    return VERSION


# ── IV percentile (3.6) ────────────────────────────────────────────────────
@app.get("/api/iv-percentile")
async def iv_percentile(symbol: str = Query(...), days: int = Query(30, ge=1, le=365)):
    sym = _validate_symbol(symbol)
    return snapshots.get_iv_percentile(sym, days)


# ── Calendar / multi-expiry (3.1) ──────────────────────────────────────────
@app.get("/api/calendar")
async def calendar(symbol: str = Query(...), maxExpiries: int = Query(6, ge=1, le=12)):
    """One row per expiry. NSE's option-chain endpoint returns data for only
    one expiry per call, so we make N parallel fetches (bounded by the NSE
    semaphore). The first fetch (no expiry argument) returns the default
    expiry plus the full expiry list — we reuse it for the first row."""
    sym = _validate_symbol(symbol)
    try:
        first_raw = await _nse_fetch_option_chain(sym, None)
    except Exception as e:
        log.error(f"[Main] /api/calendar first fetch failed for {sym}: {e}")
        raise HTTPException(status_code=502, detail={"error": str(e)})

    expiries = snapshots.list_expiries(first_raw, maxExpiries)
    if not expiries:
        return {"symbol": sym, "spot": 0, "expiries": []}

    # Fetch every expiry beyond the first in parallel.
    async def _row(exp_str: str):
        try:
            raw = first_raw if exp_str == expiries[0] else \
                  await _nse_fetch_option_chain(sym, datetime.strptime(exp_str, "%d-%b-%Y"))
            return snapshots.calendar_row(exp_str, raw)
        except Exception as e:
            log.warning(f"[Main] /api/calendar fetch for {sym} {exp_str} failed: {e}")
            return None

    rows = await asyncio.gather(*[_row(e) for e in expiries])
    return {
        "symbol": sym,
        "spot": snapshots._spot_from_records(first_raw),
        "expiries": [r for r in rows if r is not None],
    }


# ── Regime calendar heatmap (3.5) ──────────────────────────────────────────
@app.get("/api/regime-calendar")
async def regime_calendar(symbol: str = Query(...), days: int = Query(30, ge=1, le=180)):
    sym = _validate_symbol(symbol)
    return snapshots.get_regime_calendar(sym, days)


# ── Strike-level notes (3.4) ───────────────────────────────────────────────
class NoteIn(BaseModel):
    symbol: str
    strike: float
    body: str
    side: str | None = None  # 'CE', 'PE', or None


@app.get("/api/notes")
async def list_notes(symbol: str = Query(...)):
    sym = _validate_symbol(symbol)
    return {"symbol": sym, "notes": db.list_notes(sym)}


@app.post("/api/notes")
async def create_note(body: NoteIn):
    sym = _validate_symbol(body.symbol)
    if not body.body.strip():
        raise HTTPException(400, {"error": "body required"})
    if body.side and body.side.upper() not in ("CE", "PE"):
        raise HTTPException(400, {"error": "side must be CE, PE, or null"})
    note_id = db.upsert_note(sym, body.strike, body.side, body.body.strip())
    return {"id": note_id, "ok": True}


@app.delete("/api/notes/{note_id}")
async def remove_note(note_id: int):
    deleted = db.delete_note(note_id)
    if not deleted:
        raise HTTPException(404, {"error": "note not found"})
    return {"ok": True, "deleted": deleted}


# ── Prometheus metrics (5.2) ────────────────────────────────────────────────
@app.get("/metrics")
async def metrics():
    """Prometheus exposition format. No extra dependency.

    Includes counters (fetch totals/errors, cache hits, SSE messages), a
    duration histogram-sum, plus current DB size, snapshot counts, and
    SSE subscriber counts as gauges.
    """
    lines: list[str] = []

    def gauge(name: str, value: float | int, help_text: str, labels: dict[str, str] | None = None):
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        if labels:
            lbl = ",".join(f'{k}="{v}"' for k, v in labels.items())
            lines.append(f"{name}{{{lbl}}} {value}")
        else:
            lines.append(f"{name} {value}")

    def counter(name: str, value: float | int, help_text: str):
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} counter")
        lines.append(f"{name} {value}")

    with _metrics_lock:
        snap = dict(_METRICS)
        hist_sum = dict(_METRICS_HIST)
        hist_cnt = dict(_METRICS_HIST_COUNT)

    for k, v in snap.items():
        counter(k, v, "OI Pulse runtime counter")
    for k, v in hist_sum.items():
        counter(k, v, "OI Pulse cumulative duration seconds")
    for k, v in hist_cnt.items():
        counter(k, v, "OI Pulse observation count")

    gauge("oipulse_db_size_bytes", db.db_size_bytes(), "On-disk SQLite size")
    gauge("oipulse_market_open", 1 if scheduler.is_market_open() else 0, "Snapshot window active")
    for sym, n in snapshots.snapshot_counts().items():
        gauge("oipulse_snapshots_total", n, "Persisted snapshots per symbol", {"symbol": sym})
    for sym, subs in _subscribers.items():
        gauge("oipulse_sse_subscribers", len(subs), "Active SSE clients", {"symbol": sym})

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


if DEBUG_ENABLED:
    @app.get("/api/raw")
    async def raw(symbol: str = Query(...)):
        """Debug endpoint — returns a small sample of the raw NSE response."""
        sym = _validate_symbol(symbol)
        try:
            raw_resp = await _nse_fetch_option_chain(sym, None)
        except Exception as e:
            raise HTTPException(status_code=502, detail={"error": str(e)})
        rec = raw_resp.get("records") or {}
        data = rec.get("data") or []
        return {
            "symbol": sym,
            "topLevelKeys": list(raw_resp.keys()),
            "recordsKeys": list(rec.keys()),
            "underlyingValue": rec.get("underlyingValue"),
            "expiryDates": rec.get("expiryDates"),
            "dataLen": len(data),
            "firstRecord": data[0] if data else None,
            "uniqueExpiriesInData": sorted({
                (r.get("expiryDates") or r.get("expiryDate"))
                for r in data if (r.get("expiryDates") or r.get("expiryDate"))
            }),
        }


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "version": VERSION,
        "marketOpen": scheduler.is_market_open(),
        "snapshotCounts": snapshots.snapshot_counts(),
        "lastFetch": scheduler.LAST_FETCH,
        "autoSymbols": scheduler.SYMBOLS_TO_AUTO_SNAPSHOT,
        "intervalSec": scheduler.SNAPSHOT_INTERVAL_SEC,
        "dbPath": str(DB_PATH),
        "dbSizeBytes": db.db_size_bytes(),
        "now": datetime.now(scheduler.IST).isoformat(),
        "indexSymbols": sorted(INDEX_SYMBOLS),
        "sseSubscribers": {s: len(q) for s, q in _subscribers.items()},
        "debugEndpoints": DEBUG_ENABLED,
        "authEnabled": bool(BASIC_AUTH_USER),
    }


@app.post("/api/prune")
async def prune(days: int = Query(30, ge=1, le=3650)):
    """Delete snapshots older than `days`. Returns count removed."""
    deleted = db.prune_older_than(days)
    return {"deleted": deleted, "olderThanDays": days, "dbSizeBytes": db.db_size_bytes()}


@app.exception_handler(HTTPException)
async def http_exc_handler(request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(status_code=exc.status_code, content=detail, headers=exc.headers)
    return JSONResponse(status_code=exc.status_code, content={"error": str(detail)}, headers=exc.headers)


# ── CUTOVER DONE ─────────────────────────────────────────────────────────────
# The React UI (frontend/dist, built with base "/") is the DEFAULT root UI.
# The legacy vanilla UI stays at /legacy. Fallbacks:
#   - frontend/dist missing (un-built checkout)  → legacy serves at / as before.
#   - OIPULSE_LEGACY_ROOT=1                      → force legacy back to / (revert
#     switch; the React build, if present, is then only reachable via /legacy-free
#     deploys — re-unset to restore).
# /new remains as a compatibility alias for the React app (same dist; its
# root-absolute asset URLs resolve via the "/" mount).
from pathlib import Path as _Path  # noqa: E402
import os as _os  # noqa: E402

_HERE = _Path(__file__).parent
_PUBLIC_DIR = str(_HERE / "public")
_NEW_UI_DIR = _HERE / "frontend" / "dist"
_new_ui_ready = _NEW_UI_DIR.is_dir() and (_NEW_UI_DIR / "index.html").is_file()

app.mount("/legacy", StaticFiles(directory=_PUBLIC_DIR, html=True), name="legacy")

if _new_ui_ready:
    app.mount("/new", StaticFiles(directory=str(_NEW_UI_DIR), html=True), name="new-ui")

if _new_ui_ready and _os.getenv("OIPULSE_LEGACY_ROOT") != "1":
    app.mount("/", StaticFiles(directory=str(_NEW_UI_DIR), html=True), name="root")
    log.info("[Main] React UI at / (legacy at /legacy)")
else:
    app.mount("/", StaticFiles(directory=_PUBLIC_DIR, html=True), name="static")
    if not _new_ui_ready:
        log.info("[Main] frontend/dist not built — legacy UI at /")
    else:
        log.info("[Main] OIPULSE_LEGACY_ROOT=1 — legacy UI forced at /")
