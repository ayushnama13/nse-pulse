"""DuckDB / Parquet columnar layer.

SQLite stays the system of record (transactional UPSERTs). After each EOD run
we also dump the heavy time-series tables to Parquet partitioned by date —
DuckDB then reads these for analytical queries 10-100× faster than SQLite.

The user-facing entry points:

    sync_to_parquet()                       — write latest snapshot's rows out
    sync_all_to_parquet(rebuild=False)      — backfill entire history
    duckdb_query("SELECT ... FROM ...")     — run SQL against the Parquet store
    query_bhavcopy_range(from_, to_)        — pandas DataFrame in one call

Why Parquet partitioned by date:
    - Column store → indicator scans on close-only touch ~10% of disk.
    - DuckDB can push predicates into Parquet metadata and skip files.
    - Composes with pandas / Polars / R / DBeaver without any custom format.

Optional: install duckdb (`pip install duckdb`). If not installed, the module
imports cleanly but raises a friendly ImportError on first use.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger
from sqlalchemy import select

from ..utils.config import resolve_path
from .database import session_scope
from .models import (
    AnomalyFlags,
    BhavcopyEOD,
    EquityAdjustedEOD,
    EquityFeaturesEOD,
    IndexEOD,
    OptionChain,
)


PARQUET_ROOT = resolve_path("./data/parquet")


# Tables we mirror to Parquet — heavy time-series only, not metadata.
_MIRRORED = {
    "bhavcopy_eod": (BhavcopyEOD, "date"),
    "equity_adjusted_eod": (EquityAdjustedEOD, "date"),
    "equity_features_eod": (EquityFeaturesEOD, "date"),
    "index_eod": (IndexEOD, "date"),
    "anomaly_flags": (AnomalyFlags, "date"),
    "option_chain": (OptionChain, "snapshot_date"),
}


def _table_dir(table: str) -> Path:
    return PARQUET_ROOT / table


def _import_duckdb():
    try:
        import duckdb
        return duckdb
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "DuckDB not installed. `pip install duckdb` (already in pyproject extras)."
        ) from e


def sync_to_parquet(target_date: Optional[date] = None) -> dict[str, int]:
    """Mirror the rows for `target_date` (or latest date with any data) to Parquet.

    Returns a {table: rows_written} dict.
    """
    counts: dict[str, int] = {}
    PARQUET_ROOT.mkdir(parents=True, exist_ok=True)

    for table, (Model, date_col) in _MIRRORED.items():
        col = getattr(Model, date_col)
        with session_scope() as s:
            d = target_date or s.execute(
                select(col).order_by(col.desc()).limit(1)
            ).scalar()
            if d is None:
                counts[table] = 0
                continue
            df = pd.read_sql(select(Model).where(col == d), s.connection())
        if df.empty:
            counts[table] = 0
            continue
        out_dir = _table_dir(table) / f"date={d.isoformat()}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "part-0.parquet"
        df.to_parquet(out_file, index=False)
        counts[table] = len(df)
    logger.info("Parquet sync: {}", counts)
    return counts


def sync_all_to_parquet(rebuild: bool = False) -> dict[str, int]:
    """Backfill the entire history. Use `rebuild=True` to wipe + rewrite.

    For each mirrored table, iterates distinct dates and writes one Parquet per date.
    """
    counts: dict[str, int] = {}
    PARQUET_ROOT.mkdir(parents=True, exist_ok=True)
    for table, (Model, date_col) in _MIRRORED.items():
        if rebuild:
            tdir = _table_dir(table)
            if tdir.exists():
                for p in tdir.rglob("*"):
                    if p.is_file():
                        p.unlink()
        col = getattr(Model, date_col)
        with session_scope() as s:
            dates = [r[0] for r in s.execute(select(col).distinct().order_by(col)).all()]
        total = 0
        for d in dates:
            with session_scope() as s:
                df = pd.read_sql(select(Model).where(col == d), s.connection())
            if df.empty:
                continue
            out_dir = _table_dir(table) / f"date={d.isoformat()}"
            out_dir.mkdir(parents=True, exist_ok=True)
            df.to_parquet(out_dir / "part-0.parquet", index=False)
            total += len(df)
        counts[table] = total
    logger.info("Parquet backfill: {}", counts)
    return counts


def duckdb_connection():
    """Returns a fresh DuckDB connection with all mirrored tables registered as views."""
    duckdb = _import_duckdb()
    conn = duckdb.connect(":memory:")
    for table in _MIRRORED:
        tdir = _table_dir(table)
        if tdir.exists() and any(tdir.rglob("*.parquet")):
            glob = str(tdir / "**" / "*.parquet")
            conn.execute(
                f"CREATE VIEW {table} AS SELECT * FROM read_parquet('{glob}', hive_partitioning=1)"
            )
    return conn


def duckdb_query(sql: str) -> pd.DataFrame:
    """Run an arbitrary SQL query against the Parquet store; returns a DataFrame."""
    conn = duckdb_connection()
    try:
        return conn.execute(sql).fetchdf()
    finally:
        conn.close()


def query_bhavcopy_range(from_date: date, to_date: date,
                         symbols: list[str] | None = None) -> pd.DataFrame:
    """Common case: full bhavcopy slice between two dates, optionally filtered to symbols.

    Falls back to SQLite if Parquet isn't available yet.
    """
    parquet_present = (_table_dir("bhavcopy_eod")).exists() and any(
        (_table_dir("bhavcopy_eod")).rglob("*.parquet")
    )
    if parquet_present:
        sym_clause = ""
        if symbols:
            quoted = ",".join(f"'{s.upper()}'" for s in symbols)
            sym_clause = f"AND symbol IN ({quoted})"
        return duckdb_query(
            f"SELECT * FROM bhavcopy_eod WHERE date BETWEEN '{from_date}' AND '{to_date}' "
            f"{sym_clause} ORDER BY date, symbol"
        )

    # Fallback to SQLite.
    logger.info("Parquet store empty; falling back to SQLite for bhavcopy range query.")
    from .database import get_engine
    stmt = select(BhavcopyEOD).where(
        BhavcopyEOD.date >= from_date, BhavcopyEOD.date <= to_date
    )
    if symbols:
        stmt = stmt.where(BhavcopyEOD.symbol.in_([s.upper() for s in symbols]))
    return pd.read_sql(stmt.order_by(BhavcopyEOD.date, BhavcopyEOD.symbol), get_engine())
