"""Engine, session factory, and idempotent upsert helper (SQLite ON CONFLICT)."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Iterator, Type

from loguru import logger
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..utils import config as _cfg
from . import models_extra  # noqa: F401  (registers extra tables on Base)
from .models import Base


_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    db_path = _cfg.resolve_path(_cfg.get_config()["storage"]["db_path"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{db_path}"
    _ENGINE = create_engine(url, future=True)

    @event.listens_for(_ENGINE, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA busy_timeout=30000")  # several processes share this DB
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return _ENGINE


def get_session_factory() -> sessionmaker[Session]:
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SESSION_FACTORY


@contextmanager
def session_scope() -> Iterator[Session]:
    s = get_session_factory()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db() -> None:
    """Create all tables if they do not exist."""
    Base.metadata.create_all(get_engine())
    logger.info("Database initialized at {}", get_engine().url)


def upsert_records(
    model: Type[Base],
    records: Iterable[dict],
    *,
    conflict_keys: list[str] | None = None,
    update_columns: list[str] | None = None,
    chunk_size: int = 1000,
) -> int:
    """SQLite UPSERT (INSERT ... ON CONFLICT DO UPDATE).

    Args:
        model: SQLAlchemy model class.
        records: iterable of dicts (one per row).
        conflict_keys: PK column names; defaults to model's primary keys.
        update_columns: cols to overwrite on conflict; defaults to all non-key non-created_at.
    Returns:
        number of rows submitted (not necessarily written, since ON CONFLICT may no-op).
    """
    rows = list(records)
    if not rows:
        return 0

    table = model.__table__
    pk_cols = [c.name for c in table.primary_key.columns]
    conflict = conflict_keys or pk_cols
    if not conflict:
        raise ValueError(f"{model.__name__} has no primary key — cannot upsert.")

    all_cols = [c.name for c in table.columns]
    if update_columns is None:
        update_columns = [c for c in all_cols if c not in conflict and c != "created_at"]

    total = 0
    with session_scope() as s:
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            stmt = sqlite_insert(table).values(chunk)
            if update_columns:
                stmt = stmt.on_conflict_do_update(
                    index_elements=conflict,
                    set_={c: getattr(stmt.excluded, c) for c in update_columns},
                )
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=conflict)
            s.execute(stmt)
            total += len(chunk)
    return total


def insert_ignore(model: Type[Base], records: Iterable[dict], conflict_keys: list[str]) -> int:
    """INSERT ... ON CONFLICT DO NOTHING. Use for tables with surrogate PK + unique constraint."""
    rows = list(records)
    if not rows:
        return 0
    with session_scope() as s:
        stmt = sqlite_insert(model.__table__).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=conflict_keys)
        s.execute(stmt)
    return len(rows)
