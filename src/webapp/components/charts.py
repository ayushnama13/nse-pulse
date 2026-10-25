"""Plotly chart builders. Each returns a Figure for st.plotly_chart()."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def price_chart(ohlc: pd.DataFrame, features: pd.DataFrame | None = None,
                corp_actions: pd.DataFrame | None = None,
                title: str = "") -> go.Figure:
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.62, 0.18, 0.20],
        vertical_spacing=0.04,
        specs=[[{"type": "candlestick"}], [{"type": "bar"}], [{"type": "scatter"}]],
    )

    fig.add_trace(go.Candlestick(
        x=ohlc["date"], open=ohlc["open"], high=ohlc["high"],
        low=ohlc["low"], close=ohlc["close"], name="OHLC",
    ), row=1, col=1)

    if features is not None and not features.empty:
        f = features.set_index("date")
        for col, color in (("sma_20", "#2196F3"), ("sma_50", "#FFC107"), ("sma_200", "#9C27B0")):
            if col in f.columns and f[col].notna().any():
                fig.add_trace(go.Scatter(x=f.index, y=f[col], name=col.upper(),
                                         line=dict(width=1, color=color)), row=1, col=1)
        if {"bb_upper", "bb_lower"}.issubset(f.columns):
            fig.add_trace(go.Scatter(x=f.index, y=f["bb_upper"], name="BB upper",
                                     line=dict(width=1, dash="dot", color="#888")), row=1, col=1)
            fig.add_trace(go.Scatter(x=f.index, y=f["bb_lower"], name="BB lower",
                                     line=dict(width=1, dash="dot", color="#888"),
                                     fill="tonexty", fillcolor="rgba(120,120,120,0.08)"),
                          row=1, col=1)

    fig.add_trace(go.Bar(x=ohlc["date"], y=ohlc["volume"], name="Volume",
                         marker_color="#26A69A"), row=2, col=1)

    if features is not None and "rsi_14" in features.columns:
        fig.add_trace(go.Scatter(x=features["date"], y=features["rsi_14"],
                                 name="RSI(14)", line=dict(color="#E91E63")), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#777", row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#777", row=3, col=1)

    if corp_actions is not None and not corp_actions.empty:
        for _, ev in corp_actions.iterrows():
            fig.add_vline(x=ev["ex_date"], line_dash="dash", line_color="#FF5722",
                          opacity=0.5, row=1, col=1,
                          annotation_text=ev["action_type"][:1])

    fig.update_layout(
        title=title, height=700, showlegend=True, xaxis_rangeslider_visible=False,
        margin=dict(t=40, b=20, l=10, r=10),
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
    return fig


def oi_heatmap(chain: pd.DataFrame, spot: float | None) -> go.Figure:
    if chain.empty:
        return go.Figure()
    pivot = chain.pivot_table(index="strike_price", columns="option_type",
                              values="oi", aggfunc="sum").fillna(0)
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True,
                        subplot_titles=("Calls (OI)", "Puts (OI)"))
    if "CE" in pivot.columns:
        fig.add_trace(go.Bar(y=pivot.index, x=pivot["CE"], orientation="h",
                             marker_color="#26A69A", name="CE OI"), row=1, col=1)
    if "PE" in pivot.columns:
        fig.add_trace(go.Bar(y=pivot.index, x=pivot["PE"], orientation="h",
                             marker_color="#EF5350", name="PE OI"), row=1, col=2)
    if spot is not None:
        fig.add_hline(y=spot, line_dash="dash", line_color="#FFC107",
                      annotation_text=f"Spot {spot:.1f}", annotation_position="top right")
    fig.update_layout(height=600, showlegend=False, margin=dict(t=40, b=20, l=10, r=10))
    return fig


def flow_chart(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.5, 0.5],
                        subplot_titles=("Daily Net Flow", "Cumulative Net Flow"),
                        vertical_spacing=0.08)
    if df.empty:
        return fig
    for cat, color in (("FII", "#2196F3"), ("DII", "#FFC107")):
        sub = df[df["category"] == cat].sort_values("date")
        if sub.empty:
            continue
        fig.add_trace(go.Bar(x=sub["date"], y=sub["net_value"], name=f"{cat} net",
                             marker_color=color), row=1, col=1)
        fig.add_trace(go.Scatter(x=sub["date"], y=sub["net_value"].cumsum(),
                                 name=f"{cat} cum", line=dict(color=color, width=2)),
                      row=2, col=1)
    fig.update_layout(height=600, barmode="group",
                      margin=dict(t=40, b=20, l=10, r=10))
    return fig


def index_chart(history: pd.DataFrame, features: pd.DataFrame | None = None) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3],
                        subplot_titles=("Index", "RSI(14)"),
                        vertical_spacing=0.08)
    if not history.empty:
        fig.add_trace(go.Scatter(x=history["date"], y=history["close"],
                                 name="Close", line=dict(color="#2196F3", width=2)),
                      row=1, col=1)
    if features is not None and not features.empty:
        for col, color in (("sma_50", "#FFC107"), ("sma_200", "#9C27B0")):
            if col in features.columns:
                fig.add_trace(go.Scatter(x=features["date"], y=features[col],
                                         name=col.upper(), line=dict(width=1, color=color)),
                              row=1, col=1)
        if "rsi_14" in features.columns:
            fig.add_trace(go.Scatter(x=features["date"], y=features["rsi_14"],
                                     name="RSI(14)", line=dict(color="#E91E63")),
                          row=2, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="#777", row=2, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="#777", row=2, col=1)
    fig.update_layout(height=600, margin=dict(t=40, b=20, l=10, r=10))
    fig.update_yaxes(range=[0, 100], row=2, col=1)
    return fig
