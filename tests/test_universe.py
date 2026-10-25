"""Named universes."""
from __future__ import annotations

from src.storage.database import init_db
from src.universe import get_universe, list_universes, set_universe


def test_set_get_universe_roundtrip():
    init_db()
    n = set_universe("NIFTY_5", ["RELIANCE", "TCS", "INFY", "HDFC", "ICICIBANK"])
    assert n == 5
    out = get_universe("NIFTY_5")
    assert out == ["HDFC", "ICICIBANK", "INFY", "RELIANCE", "TCS"]


def test_replace_universe():
    init_db()
    set_universe("U", ["A", "B"])
    set_universe("U", ["C", "D", "E"])
    assert get_universe("U") == ["C", "D", "E"]


def test_list_universes():
    init_db()
    set_universe("U1", ["A"])
    set_universe("U2", ["B"])
    assert set(list_universes()) >= {"U1", "U2"}
