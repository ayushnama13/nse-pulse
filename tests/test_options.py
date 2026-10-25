"""Black-Scholes Greeks: spot-check known properties without external libs."""
import math

from src.preprocess.options_analytics import _bs_price, _greeks, _solve_iv, _max_pain
import pandas as pd


def test_atm_call_put_parity():
    # At-the-money parity: C - P = S - K e^{-rT}
    S, K, T, r, sigma = 100.0, 100.0, 0.25, 0.07, 0.2
    c = _bs_price(S, K, T, r, sigma, True)
    p = _bs_price(S, K, T, r, sigma, False)
    expected = S - K * math.exp(-r * T)
    assert abs((c - p) - expected) < 1e-6


def test_call_delta_in_zero_one():
    g = _greeks(100, 100, 0.25, 0.07, 0.2, True)
    assert 0.0 <= g["delta"] <= 1.0
    assert g["gamma"] >= 0
    assert g["vega"] >= 0


def test_put_delta_negative():
    g = _greeks(100, 100, 0.25, 0.07, 0.2, False)
    assert -1.0 <= g["delta"] <= 0.0


def test_iv_solver_recovers_input_sigma():
    S, K, T, r, sigma = 100.0, 105.0, 0.5, 0.07, 0.25
    price = _bs_price(S, K, T, r, sigma, True)
    solved = _solve_iv(price, S, K, T, r, True)
    assert solved is not None
    assert abs(solved - sigma) < 5e-3


def test_max_pain_simple():
    """Symmetric chain: max pain should be the central strike."""
    rows = []
    for k, oi_ce, oi_pe in [(95, 100, 50), (100, 80, 80), (105, 50, 100)]:
        rows.append({"strike_price": k, "option_type": "CE", "oi": oi_ce})
        rows.append({"strike_price": k, "option_type": "PE", "oi": oi_pe})
    df = pd.DataFrame(rows)
    assert _max_pain(df) == 100.0
