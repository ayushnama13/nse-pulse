"""News feed scraped from financial RSS sources."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from src.access.queries import get_news


st.set_page_config(page_title="News", layout="wide")
st.title("Markets news")

symbol = st.sidebar.text_input("Filter by symbol (optional)", value="").strip().upper() or None
limit = st.sidebar.slider("Items", min_value=20, max_value=500, value=100, step=20)

news = get_news(symbol=symbol, limit=limit)
if news.empty:
    st.info("No news yet. Run `python orchestrator.py --scrapers news`.")
else:
    for _, row in news.iterrows():
        st.markdown(
            f"**[{row['title']}]({row['link']})**  \n"
            f"*{row['source']}* · {row['published_at']}"
            + (f" · `{row['symbol']}`" if row.get("symbol") else "")
        )
        if row.get("summary"):
            st.caption(row["summary"][:280] + ("..." if len(row["summary"]) > 280 else ""))
        st.divider()
