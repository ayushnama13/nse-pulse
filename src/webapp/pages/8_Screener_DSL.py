"""DSL Screener: write a one-line query, save it, re-use it later, or alert on it."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st

from src.screener import dsl as screener_dsl, engine as screener_engine


st.set_page_config(page_title="Screener (DSL)", layout="wide")
st.title("Screener — query language")

st.markdown(
    """
    Write a filter using the small DSL. Fields are columns of the joined
    `BhavcopyEOD + EquityFeaturesEOD + AnomalyFlags + SymbolSector` table.

    Examples:
    - `rs_rating >= 85 AND close > sma_50`
    - `is_breakout_20d == 1 AND delivery_pct >= 50`
    - `sector == 'Banks' AND ret_1y BETWEEN [-20, 50]`
    - `volume_spike_z > 2 AND gap_pct > 0`
    """
)

col1, col2 = st.columns([3, 1])
with col1:
    expression = st.text_area(
        "Expression",
        value="rs_rating >= 80 AND close > sma_50",
        height=80,
    )
with col2:
    limit = st.number_input("Max rows", min_value=10, max_value=2000, value=200, step=10)
    universe = st.text_input("Universe (optional)", value="")

run_btn = st.button("Run", type="primary")
save_col, name_col = st.columns([1, 3])
with save_col:
    save_btn = st.button("Save")
with name_col:
    save_name = st.text_input("Save as", value="my_screen", label_visibility="collapsed")

if run_btn or save_btn:
    try:
        if save_btn:
            screener_engine.save(save_name, expression)
            st.success(f"Saved as '{save_name}'.")
        df = screener_engine.run(expression, universe=universe or None, limit=int(limit))
        st.markdown(f"**{len(df)}** matches")
        if not df.empty:
            preferred_cols = [c for c in [
                "symbol", "sector", "close", "rs_rating", "ret_1m", "ret_1y",
                "rsi_14", "volume_spike_z", "gap_pct", "is_breakout_20d",
                "delivery_pct", "dist_high_52w_pct",
            ] if c in df.columns]
            other_cols = [c for c in df.columns if c not in preferred_cols]
            st.dataframe(df[preferred_cols + other_cols], use_container_width=True,
                         hide_index=True, height=560)
            csv = df.to_csv(index=False).encode()
            st.download_button("Export CSV", csv, file_name="screen.csv", mime="text/csv")
    except screener_dsl.ScreenerError as e:
        st.error(f"DSL error: {e}")
    except Exception as e:
        st.exception(e)

st.divider()
st.subheader("Saved screens")
saved = screener_engine.list_saved()
if not saved:
    st.caption("None yet.")
else:
    for row in saved:
        with st.expander(f"{row['name']}  ·  updated {row['updated_at']}"):
            st.code(row["expression"], language="text")
            if row["description"]:
                st.caption(row["description"])
            c1, c2 = st.columns(2)
            if c1.button(f"Run '{row['name']}'", key=f"run_{row['name']}"):
                st.session_state["__rerun_expr"] = row["expression"]
                st.experimental_rerun()
            if c2.button(f"Delete '{row['name']}'", key=f"del_{row['name']}"):
                screener_engine.delete(row["name"])
                st.experimental_rerun()
