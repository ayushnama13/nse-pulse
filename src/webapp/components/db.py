"""Cached read helpers for Streamlit pages. 60s TTL keeps page nav snappy."""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st

from src.access import queries as Q


@st.cache_data(ttl=60, show_spinner=False)
def list_symbols() -> list[str]:
    return Q.list_symbols()


@st.cache_data(ttl=60, show_spinner=False)
def list_indices() -> list[str]:
    return Q.list_indices()


@st.cache_data(ttl=60, show_spinner=False)
def latest_snapshot() -> pd.DataFrame:
    return Q.latest_eod_snapshot()


@st.cache_data(ttl=60, show_spinner=False)
def get_ohlc(symbol: str, from_date: Optional[date] = None, to_date: Optional[date] = None,
             adjusted: bool = True) -> pd.DataFrame:
    return Q.get_ohlc(symbol, from_date, to_date, adjusted=adjusted)


@st.cache_data(ttl=60, show_spinner=False)
def get_features(symbol: str, from_date: Optional[date] = None,
                 to_date: Optional[date] = None) -> pd.DataFrame:
    return Q.get_equity_features(symbol, from_date, to_date)


@st.cache_data(ttl=60, show_spinner=False)
def get_corp_actions(symbol: Optional[str] = None) -> pd.DataFrame:
    return Q.get_corporate_actions(symbol)


@st.cache_data(ttl=60, show_spinner=False)
def get_index_history(name: str) -> pd.DataFrame:
    return Q.get_index_history(name)


@st.cache_data(ttl=60, show_spinner=False)
def get_index_features(name: str) -> pd.DataFrame:
    return Q.get_index_features(name)


@st.cache_data(ttl=60, show_spinner=False)
def get_option_chain(symbol: str, snapshot_date: Optional[date] = None) -> pd.DataFrame:
    return Q.get_option_chain(symbol, snapshot_date)


@st.cache_data(ttl=60, show_spinner=False)
def get_option_features(symbol: str, snapshot_date: Optional[date] = None) -> pd.DataFrame:
    return Q.get_option_features(symbol, snapshot_date)


@st.cache_data(ttl=60, show_spinner=False)
def get_option_summary(symbol: str) -> pd.DataFrame:
    return Q.get_option_chain_summary(symbol)


@st.cache_data(ttl=60, show_spinner=False)
def get_fii_dii(from_date: Optional[date] = None, to_date: Optional[date] = None) -> pd.DataFrame:
    return Q.get_fii_dii(from_date, to_date)


@st.cache_data(ttl=60, show_spinner=False)
def get_flow_features() -> pd.DataFrame:
    return Q.get_flow_features()


@st.cache_data(ttl=60, show_spinner=False)
def get_bulk_deals(symbol: Optional[str] = None,
                   from_date: Optional[date] = None,
                   to_date: Optional[date] = None) -> pd.DataFrame:
    return Q.get_bulk_deals(symbol, from_date, to_date)


@st.cache_data(ttl=30, show_spinner=False)
def get_scraper_runs(limit: int = 200) -> pd.DataFrame:
    return Q.get_scraper_runs(limit)
