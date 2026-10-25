"""Sanity check on split/bonus/dividend adjustment factors."""
from src.preprocess.corporate_adjustments import (
    _bonus_factor,
    _dividend_amount,
    _factor_for_action,
    _split_factor,
)


def test_split_factor_parsing():
    # Face value Rs.10 to Rs.1 = 10:1 split → multiplier 10 → adj_factor = 1/10
    assert _split_factor("FV split from Rs.10 to Rs.1 - 10:1") == 10.0
    assert _factor_for_action("SPLIT", "10:1", None) == 0.1


def test_bonus_factor_parsing():
    # Bonus 1:1 → 1 new share for every 1 held → multiplier 2 → adj_factor = 0.5
    assert _bonus_factor("Bonus 1:1") == 2.0
    assert _factor_for_action("BONUS", "1:1", None) == 0.5


def test_dividend_factor_uses_prev_close():
    # Rs 10 dividend on a Rs 100 prev close → factor = 1 - 10/100 = 0.9
    f = _factor_for_action("DIVIDEND", "Final dividend Rs. 10 per share", prev_close=100.0)
    assert abs(f - 0.9) < 1e-9


def test_no_factor_falls_through_to_one():
    assert _factor_for_action("OTHER", "AGM", None) == 1.0
    assert _factor_for_action("DIVIDEND", "Dividend declared", None) == 1.0  # no amount parseable


def test_dividend_amount_parser():
    assert _dividend_amount("Rs. 12.50 per share") == 12.5
    assert _dividend_amount("INR 5") == 5.0
