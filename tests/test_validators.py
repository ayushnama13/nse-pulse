from datetime import date, time

from src.validators.checks import validate_records
from src.validators.schemas import (
    BhavcopyRow,
    BulkDealRow,
    CorpActionRow,
    FIIDIIRow,
    IndexRow,
    OptionChainRow,
)


def test_bhavcopy_accepts_good_row():
    rec = {
        "date": date(2026, 5, 8), "symbol": "RELIANCE", "series": "EQ",
        "open": 2900.0, "high": 2950.0, "low": 2880.0, "close": 2935.0,
        "volume": 1234567,
    }
    out = validate_records([rec], BhavcopyRow)
    assert len(out) == 1
    assert out[0]["symbol"] == "RELIANCE"


def test_bhavcopy_rejects_zero_price():
    bad = {
        "date": date(2026, 5, 8), "symbol": "RELIANCE", "series": "EQ",
        "open": 0.0, "high": 1, "low": 1, "close": 1, "volume": 0,
    }
    assert validate_records([bad], BhavcopyRow) == []


def test_bhavcopy_rejects_bad_symbol():
    bad = {
        "date": date(2026, 5, 8), "symbol": "with space!", "series": "EQ",
        "open": 1, "high": 1, "low": 1, "close": 1, "volume": 0,
    }
    assert validate_records([bad], BhavcopyRow) == []


def test_index_row_basic():
    rec = {"date": date(2026, 5, 8), "index_name": "NIFTY 50", "close": 22500.0}
    assert len(validate_records([rec], IndexRow)) == 1


def test_corp_action_classifies_type_post_validation():
    rec = {"symbol": "TCS", "action_type": "dividend", "ex_date": date(2026, 4, 15)}
    out = validate_records([rec], CorpActionRow)
    assert out[0]["action_type"] == "DIVIDEND"


def test_option_chain_row_rejects_bad_type():
    bad = {
        "snapshot_date": date(2026, 5, 8), "snapshot_time": time(15, 30),
        "symbol": "NIFTY", "expiry_date": date(2026, 5, 29),
        "strike_price": 22000.0, "option_type": "XX",
    }
    assert validate_records([bad], OptionChainRow) == []


def test_fii_dii_row_normalizes_category():
    rec = {"date": date(2026, 5, 8), "category": "fii", "segment": "CASH",
           "buy_value": 100.0, "sell_value": 80.0, "net_value": 20.0}
    out = validate_records([rec], FIIDIIRow)
    assert out and out[0]["category"] == "FII"


def test_bulk_deal_row_normalizes_side():
    rec = {"date": date(2026, 5, 8), "symbol": "TCS", "client_name": "X",
           "side": "buy", "quantity": 10, "avg_price": 1.0}
    out = validate_records([rec], BulkDealRow)
    assert out and out[0]["side"] == "BUY"
