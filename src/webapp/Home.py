"""Streamlit entry point. Run: streamlit run src/webapp/Home.py --server.address 127.0.0.1"""
from __future__ import annotations

import _bootstrap  # noqa: F401  (path setup)

import pandas as pd
import streamlit as st

from src.webapp.components import db


st.set_page_config(page_title="NSE Pulse", page_icon=None, layout="wide")
st.title("NSE Pulse — Home")

snapshot = db.latest_snapshot()
if snapshot.empty:
    st.warning("No data in the database yet. Run `python orchestrator.py --date today` first.")
    st.stop()

last_date = pd.to_datetime(snapshot["date"]).max().date()
st.caption(f"Latest EOD snapshot: **{last_date}** — {len(snapshot)} symbols")

# ---- Top metrics ----
total_traded = float(snapshot["turnover"].fillna(0).sum())
total_volume = int(snapshot["volume"].fillna(0).sum())
gainers = int((snapshot["close"] > snapshot["prev_close"]).sum())
losers = int((snapshot["close"] < snapshot["prev_close"]).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Symbols", len(snapshot))
c2.metric("Advances", f"{gainers}")
c3.metric("Declines", f"{losers}")
c4.metric("Turnover (Cr)", f"{total_traded / 1e7:,.0f}")

# ---- Top movers ----
st.subheader("Top movers (today)")
moved = snapshot.dropna(subset=["prev_close"]).copy()
moved["pct_chg"] = (moved["close"] / moved["prev_close"] - 1.0) * 100.0
top_g = moved.nlargest(15, "pct_chg")[["symbol", "close", "pct_chg", "volume", "delivery_pct"]]
top_l = moved.nsmallest(15, "pct_chg")[["symbol", "close", "pct_chg", "volume", "delivery_pct"]]

g_col, l_col = st.columns(2)
with g_col:
    st.markdown("**Gainers**")
    st.dataframe(top_g.style.format({"close": "{:.2f}", "pct_chg": "{:+.2f}%",
                                     "volume": "{:,.0f}", "delivery_pct": "{:.1f}%"}),
                 use_container_width=True, hide_index=True)
with l_col:
    st.markdown("**Losers**")
    st.dataframe(top_l.style.format({"close": "{:.2f}", "pct_chg": "{:+.2f}%",
                                     "volume": "{:,.0f}", "delivery_pct": "{:.1f}%"}),
                 use_container_width=True, hide_index=True)

# ---- FII/DII today ----
st.subheader("Institutional flow")
flow = db.get_fii_dii(from_date=last_date, to_date=last_date)
if flow.empty:
    st.info("No FII/DII data for today yet.")
else:
    flow["net_value_cr"] = flow["net_value"] / 1e7
    st.dataframe(flow[["category", "segment", "buy_value", "sell_value", "net_value_cr"]]
                 .style.format({"buy_value": "{:,.0f}", "sell_value": "{:,.0f}",
                                "net_value_cr": "{:+,.0f}"}),
                 use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Use the sidebar to navigate to Ticker · Screener · Indices · Option Chain · FII/DII · Deals · Data Quality")
