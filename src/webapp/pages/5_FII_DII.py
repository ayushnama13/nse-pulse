"""FII/DII flow page."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from src.webapp.components import db
from src.webapp.components.charts import flow_chart
from src.webapp.components.filters import sidebar_date_range


st.set_page_config(page_title="FII / DII", layout="wide")
st.title("FII / DII Flow")

d_from, d_to = sidebar_date_range(default_days=180)
flow = db.get_fii_dii(d_from, d_to)

if flow.empty:
    st.warning("No FII/DII data in range.")
    st.stop()

st.plotly_chart(flow_chart(flow), use_container_width=True)

st.subheader("Z-score outliers")
feats = db.get_flow_features()
if not feats.empty:
    feats = feats[(feats["date"] >= d_from) & (feats["date"] <= d_to)]
    outliers = feats[feats["zscore_20d"].abs() >= 2.0].sort_values("date", ascending=False)
    if outliers.empty:
        st.info("No |z-score| ≥ 2 days in this range.")
    else:
        st.dataframe(outliers, use_container_width=True, hide_index=True)
else:
    st.info("Run preprocessing to populate flow_features_daily.")

with st.expander("Daily rows"):
    st.dataframe(flow.sort_values("date", ascending=False), use_container_width=True, hide_index=True)
