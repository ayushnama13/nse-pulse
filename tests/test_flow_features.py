from datetime import date

from src.preprocess import flow_features
from src.storage.database import init_db, upsert_records, session_scope
from src.storage.models import FIIDIIDaily, FlowFeaturesDaily


def test_flow_features_compute_writes_rows():
    init_db()
    seed = [
        {
            "date": date(2026, 4, i + 1),
            "category": "FII", "segment": "CASH",
            "buy_value": 1000.0 + i, "sell_value": 800.0,
            "net_value": 200.0 + i,
        }
        for i in range(25)
    ]
    upsert_records(FIIDIIDaily, seed)
    written = flow_features.compute()
    assert written == 25
    with session_scope() as s:
        n = s.query(FlowFeaturesDaily).count()
    assert n == 25
