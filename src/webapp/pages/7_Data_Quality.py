"""Data Quality: scraper run log + row-count health."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import streamlit as st

from src.webapp.components import db


st.set_page_config(page_title="Data Quality", layout="wide")
st.title("Data Quality")

runs = db.get_scraper_runs(limit=500)
if runs.empty:
    st.info("No runs logged yet.")
    st.stop()

# ---- Last successful run per scraper ----
st.subheader("Last successful run per scraper")
ok = runs[runs["status"] == "success"].copy()
last_ok = ok.sort_values("run_started_at").groupby("scraper").tail(1)
last_ok = last_ok[["scraper", "target_date", "run_finished_at", "rows_fetched", "rows_stored"]] \
    .sort_values("scraper")
st.dataframe(last_ok, use_container_width=True, hide_index=True)

# ---- Failure tail ----
st.subheader("Recent failures")
fails = runs[runs["status"] == "failure"].head(20)
if fails.empty:
    st.success("No failures in the last 500 runs.")
else:
    st.dataframe(fails[["scraper", "target_date", "run_started_at", "error"]],
                 use_container_width=True, hide_index=True)

# ---- Row-count trend ----
st.subheader("Row-count trend")
trend = runs[runs["status"] == "success"].copy()
trend["run_started_at"] = pd.to_datetime(trend["run_started_at"])
pivot = trend.pivot_table(index="run_started_at", columns="scraper",
                          values="rows_fetched", aggfunc="sum")
if not pivot.empty:
    st.line_chart(pivot)

with st.expander("All recent runs"):
    st.dataframe(runs.head(200), use_container_width=True, hide_index=True)
