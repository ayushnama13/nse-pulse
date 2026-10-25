"""Shared pytest fixtures."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Make `src.*` importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Each test gets a fresh SQLite DB at <tmp>/nse.db. Tears down config + engine cache."""
    db_path = tmp_path / "nse.db"
    # Reset config cache and patch storage.db_path before code reads it.
    from src.utils import config as cfg_mod
    cfg_mod.get_config.cache_clear()
    cfg_mod.get_endpoints.cache_clear()
    cfg_mod.get_holidays.cache_clear()

    real_get_config = cfg_mod.get_config

    def patched_get_config():
        c = dict(real_get_config())
        c["storage"] = dict(c.get("storage", {}))
        c["storage"]["db_path"] = str(db_path)
        return c

    monkeypatch.setattr(cfg_mod, "get_config", patched_get_config)

    # Reset DB engine module-level cache.
    from src.storage import database as dbmod
    dbmod._ENGINE = None
    dbmod._SESSION_FACTORY = None

    yield db_path

    dbmod._ENGINE = None
    dbmod._SESSION_FACTORY = None
