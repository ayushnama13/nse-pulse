"""Ticker explorer: OHLC + indicators + corp action overlay."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from src.webapp.components import db
from src.webapp.components.charts import price_chart
from src.webapp.components.filters import sidebar_date_range, sidebar_symbol_picker


st.set_page_config(page_title="Ticker", layout="wide")
st.title("Ticker Explorer")

symbols = db.list_symbols()
sym = sidebar_symbol_picker(symbols, key="ticker_sym")
d_from, d_to = sidebar_date_range(default_days=365)

if not sym:
    st.stop()

ohlc = db.get_ohlc(sym, d_from, d_to, adjusted=True)
if ohlc.empty:
    st.warning(f"No data for {sym} in selected range.")
    st.stop()

feats = db.get_features(sym, d_from, d_to)
ca = db.get_corp_actions(sym)
if not ca.empty:
    ca = ca[(ca["ex_date"] >= d_from) & (ca["ex_date"] <= d_to)]

last = feats.iloc[-1] if not feats.empty else None
last_close = ohlc.iloc[-1]["close"]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Last close", f"{last_close:,.2f}")
if last is not None:
    if last.get("ret_1d") is not None:
        c2.metric("1d return", f"{last['ret_1d'] * 100:+.2f}%")
    if last.get("ret_1m") is not None:
        c3.metric("1m return", f"{last['ret_1m'] * 100:+.2f}%")
    if last.get("rsi_14") is not None:
        c4.metric("RSI(14)", f"{last['rsi_14']:.1f}")
    if last.get("dist_high_52w_pct") is not None:
        c5.metric("from 52w high", f"{last['dist_high_52w_pct']:+.1f}%")

st.plotly_chart(price_chart(ohlc, feats, ca, title=sym), use_container_width=True)

with st.expander("Corporate actions"):
    st.dataframe(ca[["ex_date", "action_type", "description"]] if not ca.empty
                 else "(none in range)", use_container_width=True)

with st.expander("Features (last 30 rows)"):
    st.dataframe(feats.tail(30), use_container_width=True)

with st.expander("Raw OHLC (last 30 rows)"):
    st.dataframe(ohlc.tail(30), use_container_width=True)
