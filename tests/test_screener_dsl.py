"""Screener DSL parsing + evaluation."""
from __future__ import annotations

import pandas as pd
import pytest

from src.screener.dsl import ScreenerError, evaluate, parse


@pytest.fixture
def df():
    return pd.DataFrame({
        "symbol": ["A", "B", "C", "D"],
        "close": [100.0, 200.0, 50.0, 300.0],
        "rsi_14": [25.0, 70.0, 80.0, 55.0],
        "rs_rating": [90, 50, 20, 75],
        "sector": ["Banks", "IT", "Banks", "Energy"],
        "is_breakout_20d": [1, 0, 0, 1],
    })


def test_basic_gt(df):
    mask = evaluate(parse("close > 100"), df)
    assert mask.tolist() == [False, True, False, True]


def test_and_or(df):
    mask = evaluate(parse("close > 100 AND rsi_14 < 75"), df)
    assert mask.tolist() == [False, True, False, True]
    mask2 = evaluate(parse("close > 250 OR rsi_14 < 30"), df)
    assert mask2.tolist() == [True, False, False, True]


def test_not(df):
    mask = evaluate(parse("NOT (close > 100)"), df)
    assert mask.tolist() == [True, False, True, False]


def test_between(df):
    mask = evaluate(parse("rsi_14 BETWEEN [30, 75]"), df)
    assert mask.tolist() == [False, True, False, True]


def test_in_strings(df):
    mask = evaluate(parse("sector IN ['Banks', 'IT']"), df)
    assert mask.tolist() == [True, True, True, False]


def test_string_equality(df):
    mask = evaluate(parse("sector == 'Banks'"), df)
    assert mask.tolist() == [True, False, True, False]


def test_complex_query(df):
    mask = evaluate(
        parse("rs_rating >= 80 AND (close < 100 OR is_breakout_20d == 1)"), df
    )
    assert mask.tolist() == [True, False, False, False]


def test_unknown_field_raises(df):
    with pytest.raises(ScreenerError):
        evaluate(parse("nonexistent > 0"), df)


def test_bad_syntax_raises():
    with pytest.raises(ScreenerError):
        parse("close >>> 100")
