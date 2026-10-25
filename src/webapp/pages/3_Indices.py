"""Index dashboard."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from src.webapp.components import db
from src.webapp.components.charts import index_chart
from src.webapp.components.filters import sidebar_index_picker


st.set_page_config(page_title="Indices", layout="wide")
st.title("Index Dashboard")

indices = db.list_indices()
name = sidebar_index_picker(indices, key="idx_pick")
if not name:
    st.stop()

history = db.get_index_history(name)
features = db.get_index_features(name)

if history.empty:
    st.warning(f"No history for {name}")
    st.stop()

last = history.iloc[-1]
last_feat = features.iloc[-1] if not features.empty else None

c1, c2, c3, c4 = st.columns(4)
c1.metric("Last close", f"{last['close']:,.2f}")
if last.get("pe") is not None:
    c2.metric("PE", f"{last['pe']:.2f}" if last["pe"] else "—")
if last.get("pb") is not None:
    c3.metric("PB", f"{last['pb']:.2f}" if last["pb"] else "—")
if last.get("div_yield") is not None:
    c4.metric("Div yield", f"{last['div_yield']:.2f}" if last["div_yield"] else "—")

if last_feat is not None:
    c1, c2, c3, c4 = st.columns(4)
    if last_feat.get("ret_1m") is not None:
        c1.metric("1m return", f"{last_feat['ret_1m'] * 100:+.2f}%")
    if last_feat.get("ret_1y") is not None:
        c2.metric("1y return", f"{last_feat['ret_1y'] * 100:+.2f}%")
    if last_feat.get("rsi_14") is not None:
        c3.metric("RSI(14)", f"{last_feat['rsi_14']:.1f}")
    if last_feat.get("drawdown_pct") is not None:
        c4.metric("Drawdown", f"{last_feat['drawdown_pct']:+.1f}%")

st.plotly_chart(index_chart(history, features), use_container_width=True)

with st.expander("PE / PB / DY trend"):
    pdf = history[["date", "pe", "pb", "div_yield"]].dropna(how="all", subset=["pe", "pb", "div_yield"])
    if pdf.empty:
        st.write("(No fundamental history captured.)")
    else:
        st.line_chart(pdf.set_index("date"))
