"""Portfolio: import broker tradebook CSV → holdings, P&L, XIRR, sector exposure."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from src.portfolio import analytics, importer


st.set_page_config(page_title="Portfolio", layout="wide")
st.title("Portfolio")

portfolio = st.sidebar.text_input("Portfolio name", value="default")

st.subheader("Import broker tradebook")
broker = st.selectbox("Broker", options=[None, *importer.BROKERS],
                      format_func=lambda x: "auto-detect" if x is None else x)
uploaded = st.file_uploader("CSV file", type=["csv"])
if uploaded is not None:
    tmp = Path("/tmp") / uploaded.name
    tmp.write_bytes(uploaded.read())
    try:
        n = importer.import_csv(tmp, portfolio=portfolio, broker=broker)
        st.success(f"Imported {n} trades.")
    except Exception as e:
        st.exception(e)

st.divider()
st.subheader("Holdings (mark-to-market)")
h = analytics.holdings(portfolio)
if h.empty:
    st.info("No holdings yet. Import a tradebook above.")
else:
    st.dataframe(
        h.style.format({
            "quantity": "{:,.2f}",
            "avg_cost": "{:,.2f}",
            "cost_basis": "{:,.0f}",
            "mtm_price": "{:,.2f}",
            "market_value": "{:,.0f}",
            "unrealized_pnl": "{:+,.0f}",
            "unrealized_pct": "{:+.2f}%",
            "realized_pnl": "{:+,.0f}",
        }, na_rep="—"),
        use_container_width=True, hide_index=True, height=500,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market value", f"₹{h['market_value'].sum():,.0f}")
    c2.metric("Unrealized P&L", f"₹{h['unrealized_pnl'].sum():+,.0f}")
    c3.metric("Realized P&L", f"₹{h['realized_pnl'].sum():+,.0f}")
    xirr_val = analytics.xirr(portfolio)
    c4.metric("XIRR", f"{xirr_val * 100:.2f}%" if xirr_val is not None else "—")

    st.divider()
    st.subheader("Sector exposure")
    exp = analytics.sector_exposure(portfolio)
    if not exp.empty:
        st.dataframe(
            exp.style.format({"exposure_value": "{:,.0f}", "exposure_pct": "{:.2f}%"}),
            use_container_width=True, hide_index=True,
        )
