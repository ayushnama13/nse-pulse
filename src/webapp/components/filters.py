"""Sidebar widgets shared across pages."""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st


def sidebar_date_range(default_days: int = 365) -> tuple[date, date]:
    today = date.today()
    default_from = today - timedelta(days=default_days)
    with st.sidebar:
        st.markdown("### Date range")
        d_from = st.date_input("From", value=default_from, key="filter_from")
        d_to = st.date_input("To", value=today, key="filter_to")
    if d_from > d_to:
        d_from, d_to = d_to, d_from
    return d_from, d_to


def sidebar_symbol_picker(symbols: list[str], key: str = "sym",
                          default: str | None = None) -> str | None:
    if not symbols:
        st.sidebar.warning("No symbols found in DB. Run the pipeline first.")
        return None
    if default and default in symbols:
        idx = symbols.index(default)
    else:
        idx = 0
    return st.sidebar.selectbox("Symbol", options=symbols, index=idx, key=key)


def sidebar_index_picker(indices: list[str], key: str = "idx") -> str | None:
    if not indices:
        st.sidebar.warning("No indices found in DB.")
        return None
    return st.sidebar.selectbox("Index", options=indices, index=0, key=key)
