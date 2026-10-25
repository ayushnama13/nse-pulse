"""Screener: filter the latest snapshot by indicator thresholds."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import streamlit as st

from src.webapp.components import db


st.set_page_config(page_title="Screener", layout="wide")
st.title("Screener")

snap = db.latest_snapshot()
if snap.empty:
    st.warning("No snapshot data — run the pipeline first.")
    st.stop()

# Pull features for the same date.
last_date = pd.to_datetime(snap["date"]).max().date()
st.caption(f"As of **{last_date}** — {len(snap)} symbols")

# ---- Filters ----
st.sidebar.markdown("### Filters")
rsi_lo, rsi_hi = st.sidebar.slider("RSI(14) range", 0, 100, (0, 100), key="scr_rsi")
mcap_min_cr = st.sidebar.number_input("Min turnover today (Cr)", min_value=0.0, value=0.0, step=10.0)
delivery_min = st.sidebar.slider("Min delivery %", 0, 100, 0, key="scr_del")
dist_high = st.sidebar.slider("Max distance from 52w high (%)", -100.0, 0.0, 0.0, step=0.5)
dist_low = st.sidebar.slider("Min distance from 52w low (%)", 0.0, 500.0, 0.0, step=1.0)
ret_1m_min = st.sidebar.number_input("Min 1m return (%)", value=-100.0, step=1.0)
above_sma200 = st.sidebar.checkbox("Close above SMA(200)")
breakout_52w = st.sidebar.checkbox("At/above 52w high")

df = snap.copy()
df["pct_chg"] = (df["close"] / df["prev_close"] - 1.0) * 100.0
df["turnover_cr"] = df["turnover"].fillna(0) / 1e7

mask = pd.Series(True, index=df.index)
if "rsi_14" in df.columns:
    mask &= df["rsi_14"].between(rsi_lo, rsi_hi).fillna(False) | df["rsi_14"].isna() & (rsi_lo == 0 and rsi_hi == 100)
if mcap_min_cr > 0:
    mask &= df["turnover_cr"] >= mcap_min_cr
if delivery_min > 0:
    mask &= df["delivery_pct"].fillna(0) >= delivery_min
if dist_high < 0 and "dist_high_52w_pct" in df.columns:
    mask &= df["dist_high_52w_pct"].fillna(-999) >= dist_high
if dist_low > 0 and "dist_low_52w_pct" in df.columns:
    mask &= df["dist_low_52w_pct"].fillna(-1) >= dist_low
if "ret_1m" in df.columns:
    mask &= (df["ret_1m"].fillna(-1) * 100.0) >= ret_1m_min
if above_sma200 and "sma_200" in df.columns:
    mask &= df["close"] > df["sma_200"].fillna(0)
if breakout_52w and "high_52w" in df.columns:
    mask &= df["close"] >= df["high_52w"].fillna(float("inf")) * 0.999

result = df[mask].copy()

display_cols = [c for c in [
    "symbol", "close", "pct_chg", "volume", "turnover_cr", "delivery_pct",
    "rsi_14", "ret_1m", "ret_1y", "dist_high_52w_pct", "dist_low_52w_pct",
    "sma_50", "sma_200", "drawdown_pct",
] if c in result.columns]

st.markdown(f"**{len(result)}** matches")
st.dataframe(
    result[display_cols].sort_values("pct_chg", ascending=False)
    .style.format({
        "close": "{:.2f}",
        "pct_chg": "{:+.2f}%",
        "volume": "{:,.0f}",
        "turnover_cr": "{:,.0f}",
        "delivery_pct": "{:.1f}%",
        "rsi_14": "{:.1f}",
        "ret_1m": "{:+.2%}",
        "ret_1y": "{:+.2%}",
        "dist_high_52w_pct": "{:+.1f}%",
        "dist_low_52w_pct": "{:+.1f}%",
        "sma_50": "{:.2f}",
        "sma_200": "{:.2f}",
        "drawdown_pct": "{:+.1f}%",
    }, na_rep="—"),
    use_container_width=True, hide_index=True, height=600,
)

csv = result[display_cols].to_csv(index=False).encode()
st.download_button("Export CSV", csv, file_name=f"screen_{last_date}.csv", mime="text/csv")
