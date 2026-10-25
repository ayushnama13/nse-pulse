"""Bulk deals feed."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from src.webapp.components import db
from src.webapp.components.filters import sidebar_date_range


st.set_page_config(page_title="Deals", layout="wide")
st.title("Bulk Deals")

d_from, d_to = sidebar_date_range(default_days=30)

symbol_filter = st.sidebar.text_input("Symbol filter (substring)", value="")
party_filter = st.sidebar.text_input("Client filter (substring)", value="")
side_filter = st.sidebar.selectbox("Side", ["ANY", "BUY", "SELL"], index=0)

deals = db.get_bulk_deals(from_date=d_from, to_date=d_to)
if deals.empty:
    st.warning("No bulk deals captured in range.")
    st.stop()

if symbol_filter:
    deals = deals[deals["symbol"].str.contains(symbol_filter.upper(), na=False)]
if party_filter:
    deals = deals[deals["client_name"].str.contains(party_filter, case=False, na=False)]
if side_filter != "ANY":
    deals = deals[deals["side"] == side_filter]

deals["value_cr"] = deals["quantity"] * deals["avg_price"] / 1e7
st.markdown(f"**{len(deals)}** deals")
st.dataframe(
    deals[["date", "symbol", "client_name", "side", "quantity", "avg_price", "value_cr"]]
    .style.format({"quantity": "{:,.0f}", "avg_price": "{:.2f}", "value_cr": "{:,.1f}"}),
    use_container_width=True, hide_index=True, height=600,
)
