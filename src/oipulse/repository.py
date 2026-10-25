"""Storage seam — the single interface every caller should use to reach persistence.

Why this exists
---------------
`db.py` is a concrete SQLite implementation. Today that's the right call (tiny
single-process workload). But "switch the database later" is a one-way door if
call sites import `db` directly and reach into SQLite-shaped behaviour.

This module is the seam that keeps that door open. It defines a narrow
`SnapshotRepository` Protocol and a `SqliteRepository` that delegates to `db.py`
unchanged. A module-level singleton `repo` is the front door. Swapping to
Postgres/Turso/DuckDB later means writing one new class that satisfies the
Protocol and reassigning `repo` — no call site changes.

Migration is incremental: new code (and the React frontend's backend touch
points) should import `repository.repo`; existing `import db` call sites keep
working and can be moved over file-by-file.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from . import db


@runtime_checkable
class SnapshotRepository(Protocol):
    """The complete persistence contract OI Pulse depends on.

    Any storage backend that implements these methods is a drop-in replacement.
    Method names/shapes mirror the dict-based snapshot the compute layer emits.
    """

    # lifecycle
    def init(self) -> None: ...
    def shutdown(self) -> None: ...

    # snapshots
    def upsert_snapshot(self, snap: dict) -> None: ...
    def list_snapshots(self, symbol: str, limit: int = 200) -> list[dict]: ...
    def latest_snapshot(self, symbol: str) -> dict | None: ...
    def snapshot_counts(self) -> dict[str, int]: ...
    def prune_older_than(self, days: int) -> int: ...
    def db_size_bytes(self) -> int: ...
    def vacuum(self) -> None: ...

    # strike-level notes
    def list_notes(self, symbol: str) -> list[dict]: ...
    def upsert_note(self, symbol: str, strike: float, side: str | None, body: str) -> int: ...
    def delete_note(self, note_id: int) -> int: ...


class SqliteRepository:
    """Default backend — thin delegation to the existing `db` module.

    Deliberately stateless: `db` owns the connection singleton. This class only
    adapts the free-function API into the object interface the Protocol defines.
    """

    def init(self) -> None:
        db.init()

    def shutdown(self) -> None:
        db.shutdown()

    def upsert_snapshot(self, snap: dict) -> None:
        db.upsert_snapshot(snap)

    def list_snapshots(self, symbol: str, limit: int = 200) -> list[dict]:
        return db.list_snapshots(symbol, limit)

    def latest_snapshot(self, symbol: str) -> dict | None:
        return db.latest_snapshot(symbol)

    def snapshot_counts(self) -> dict[str, int]:
        return db.snapshot_counts()

    def prune_older_than(self, days: int) -> int:
        return db.prune_older_than(days)

    def db_size_bytes(self) -> int:
        return db.db_size_bytes()

    def vacuum(self) -> None:
        db.vacuum()

    def list_notes(self, symbol: str) -> list[dict]:
        return db.list_notes(symbol)

    def upsert_note(self, symbol: str, strike: float, side: str | None, body: str) -> int:
        return db.upsert_note(symbol, strike, side, body)

    def delete_note(self, note_id: int) -> int:
        return db.delete_note(note_id)


# The front door. Reassign this to a different SnapshotRepository implementation
# to swap storage backends without touching any caller.
repo: SnapshotRepository = SqliteRepository()
