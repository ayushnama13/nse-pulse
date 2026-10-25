"""Raw-payload archival + schema-drift detection."""
from __future__ import annotations

from datetime import date

from src.utils import archival


def test_archive_payload_dict_writes_gz(tmp_path, monkeypatch):
    monkeypatch.setattr(archival, "_root", lambda: tmp_path)
    p = archival.archive_payload("test_scraper", {"a": 1, "b": [1, 2]},
                                 run_date=date(2026, 5, 1))
    assert p.exists()
    assert p.suffix == ".gz"


def test_archive_payload_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(archival, "_root", lambda: tmp_path)
    p = archival.archive_payload("test_scraper", b"binary blob",
                                 run_date=date(2026, 5, 1), extension="zip")
    assert p.exists()


def test_schema_fingerprint_stable():
    fp1 = archival.schema_fingerprint({"a": 1, "b": [{"x": 1, "y": 2}]})
    fp2 = archival.schema_fingerprint({"b": [{"y": 99, "x": 5}], "a": 999})
    assert fp1 == fp2, "fingerprint should depend on shape, not values"


def test_schema_fingerprint_drift():
    fp1 = archival.schema_fingerprint({"a": 1, "b": 2})
    fp2 = archival.schema_fingerprint({"a": 1, "c": 2})
    assert fp1 != fp2


def test_check_drift_first_seen_then_change(tmp_path, monkeypatch):
    monkeypatch.setattr(archival, "_root", lambda: tmp_path)
    store = tmp_path / "fp.json"

    assert archival.check_drift("test", {"a": 1}, store=store) is False  # first
    assert archival.check_drift("test", {"a": 2}, store=store) is False  # same shape
    assert archival.check_drift("test", {"a": 1, "b": 2}, store=store) is True  # drift!


def test_prune_old(tmp_path, monkeypatch):
    import os
    import time as _time
    monkeypatch.setattr(archival, "_root", lambda: tmp_path)
    p = archival.archive_payload("test", {"a": 1}, run_date=date(2026, 1, 1))
    # Backdate the file 60 days.
    old = _time.time() - 60 * 86400
    os.utime(p, (old, old))
    n = archival.prune_old(retention_days=30)
    assert n == 1
    assert not p.exists()
