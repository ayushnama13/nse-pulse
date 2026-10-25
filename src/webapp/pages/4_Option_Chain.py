"""Option chain viewer with OI heatmap, Greeks, max pain, PCR."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import streamlit as st

from src.webapp.components import db
from src.webapp.components.charts import oi_heatmap


st.set_page_config(page_title="Option Chain", layout="wide")
st.title("Option Chain")

OC_DEFAULT = ["NIFTY", "BANKNIFTY", "RELIANCE", "HDFCBANK", "INFY", "TCS"]

symbol = st.sidebar.selectbox("Symbol", OC_DEFAULT, index=0, key="oc_sym")

chain = db.get_option_chain(symbol)
if chain.empty:
    st.warning(f"No option chain snapshots for {symbol}. Run the option_chain scraper first.")
    st.stop()

# Pick most recent snapshot
latest_d = chain["snapshot_date"].max()
latest_t = chain[chain["snapshot_date"] == latest_d]["snapshot_time"].max()
chain = chain[(chain["snapshot_date"] == latest_d) & (chain["snapshot_time"] == latest_t)]

expiries = sorted(chain["expiry_date"].unique())
expiry = st.sidebar.selectbox("Expiry", expiries, index=0, key="oc_exp")
chain = chain[chain["expiry_date"] == expiry]

features = db.get_option_features(symbol, latest_d)
features = features[(features["expiry_date"] == expiry) & (features["snapshot_time"] == latest_t)]

summary = db.get_option_summary(symbol)
summary = summary[(summary["snapshot_date"] == latest_d) & (summary["expiry_date"] == expiry)]

spot = chain["spot_price"].dropna().iloc[0] if not chain["spot_price"].dropna().empty else None
st.caption(f"Snapshot: **{latest_d} {latest_t}** · Expiry: **{expiry}** · Spot: **{spot}**")

if not summary.empty:
    s = summary.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    if s.get("max_pain") is not None:
        c1.metric("Max pain", f"{s['max_pain']:.0f}")
    if s.get("pcr_oi") is not None:
        c2.metric("PCR (OI)", f"{s['pcr_oi']:.2f}")
    if s.get("pcr_volume") is not None:
        c3.metric("PCR (Vol)", f"{s['pcr_volume']:.2f}")
    if s.get("atm_iv") is not None:
        c4.metric("ATM IV", f"{s['atm_iv']:.1f}%")

st.plotly_chart(oi_heatmap(chain, spot), use_container_width=True)

# ---- Strike grid ----
st.subheader("Strike grid")
ce = chain[chain["option_type"] == "CE"].add_prefix("CE_").rename(columns={"CE_strike_price": "strike"})
pe = chain[chain["option_type"] == "PE"].add_prefix("PE_").rename(columns={"PE_strike_price": "strike"})

if not features.empty:
    fce = features[features["option_type"] == "CE"][["strike_price", "delta", "gamma", "theta", "vega", "iv"]] \
            .add_prefix("CE_").rename(columns={"CE_strike_price": "strike"})
    fpe = features[features["option_type"] == "PE"][["strike_price", "delta", "gamma", "theta", "vega", "iv"]] \
            .add_prefix("PE_").rename(columns={"PE_strike_price": "strike"})
    ce = ce.merge(fce, on="strike", how="left")
    pe = pe.merge(fpe, on="strike", how="left")

grid = pd.merge(ce, pe, on="strike", how="outer").sort_values("strike")
show_cols = [c for c in [
    "CE_oi", "CE_change_in_oi", "CE_volume", "CE_iv", "CE_delta", "CE_ltp",
    "strike",
    "PE_ltp", "PE_delta", "PE_iv", "PE_volume", "PE_change_in_oi", "PE_oi",
] if c in grid.columns]

st.dataframe(grid[show_cols], use_container_width=True, hide_index=True, height=600)
