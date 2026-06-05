"""Plotly chart builders using WTO IP Division colour palette."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# ── IP Division palette ───────────────────────────────────────────────────────
# Navy → WTO blue → teal → slate → gold → rust
WTO_COLORS = {
    "primary":   "#002F5F",   # deep navy
    "secondary": "#004C97",   # WTO blue
    "teal":      "#007B8A",   # teal
    "highlight": "#B8860B",   # dark gold
    "positive":  "#2A6E4F",   # forest green
    "negative":  "#9E2A2B",   # deep rust
    "neutral":   "#5C6B7A",   # blue-grey slate
    "bg":        "#F4F8FC",   # very light blue-white
}

_LAYOUT = dict(
    plot_bgcolor=WTO_COLORS["bg"],
    paper_bgcolor="white",
    font=dict(family="Arial, sans-serif", size=12, color="#2B2B2B"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=50, r=30, t=60, b=50),
    hovermode="x unified",
)


def _base(title: str = "", yaxis_title: str = "") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=dict(text=title, font=dict(size=14)), **_LAYOUT)
    if yaxis_title:
        fig.update_yaxes(title_text=yaxis_title, gridcolor="#E0E0E0")
    fig.update_xaxes(gridcolor="#E0E0E0")
    return fig


def _no_data(title: str) -> go.Figure:
    fig = _base(title)
    fig.add_annotation(
        text="No data available",
        xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False, font=dict(size=14, color=WTO_COLORS["neutral"]),
    )
    return fig


# ── Chart builders ────────────────────────────────────────────────────────────

def time_series_chart(
    df: pd.DataFrame, indicator_name: str, country_name: str
) -> go.Figure:
    """Multi-trace line chart: Resident / Non-Resident / Total over time."""
    title = f"{indicator_name} — {country_name}"
    if df.empty:
        return _no_data(title)

    fig = _base(title, "Number of Applications / Grants / Registrations")

    _add_line(fig, df, "resident",     "Resident",     WTO_COLORS["secondary"], "solid")
    _add_line(fig, df, "non_resident", "Non-Resident", WTO_COLORS["teal"],      "dash")
    _add_line(fig, df, "total",        "Total",        WTO_COLORS["primary"],   "solid",
              marker_symbol="diamond", width=2.5, marker_size=7)

    return fig


def _add_line(
    fig: go.Figure,
    df: pd.DataFrame,
    col: str,
    name: str,
    color: str,
    dash: str = "solid",
    marker_symbol: str = "circle",
    width: float = 2.0,
    marker_size: int = 6,
) -> None:
    if col not in df.columns or df[col].notna().sum() == 0:
        return
    fig.add_trace(go.Scatter(
        x=df["year"],
        y=df[col],
        name=name,
        mode="lines+markers",
        line=dict(color=color, width=width, dash=dash),
        marker=dict(size=marker_size, symbol=marker_symbol),
        connectgaps=False,
    ))


def resident_foreign_bar(
    df: pd.DataFrame, indicator_name: str, country_name: str
) -> go.Figure:
    """Stacked bar chart: Resident vs Non-Resident filings by year."""
    title = f"{indicator_name} — Resident vs Non-Resident ({country_name})"
    if df.empty or "resident" not in df.columns:
        return _no_data(title)

    fig = _base(title, "Number of Filings")

    fig.add_trace(go.Bar(
        x=df["year"], y=df["resident"],
        name="Resident",
        marker_color=WTO_COLORS["secondary"],
    ))
    if "non_resident" in df.columns and df["non_resident"].notna().any():
        fig.add_trace(go.Bar(
            x=df["year"], y=df["non_resident"],
            name="Non-Resident",
            marker_color=WTO_COLORS["teal"],
        ))

    fig.update_layout(barmode="stack")
    return fig


def resident_share_line(
    df: pd.DataFrame, indicator_name: str, country_name: str
) -> go.Figure:
    """Area line chart for resident share percentage."""
    title = f"Resident Share (%) — {indicator_name} ({country_name})"
    if df.empty or "resident_share_pct" not in df.columns:
        return _no_data(title)

    fig = _base(title, "Resident Share (%)")
    fig.add_trace(go.Scatter(
        x=df["year"],
        y=df["resident_share_pct"],
        name="Resident Share",
        mode="lines+markers",
        line=dict(color=WTO_COLORS["secondary"], width=2),
        fill="tozeroy",
        fillcolor="rgba(0,76,151,0.10)",
        connectgaps=False,
    ))
    fig.add_hline(
        y=50,
        line_dash="dash",
        line_color=WTO_COLORS["neutral"],
        annotation_text="50%",
        annotation_position="right",
    )
    fig.update_yaxes(range=[0, 105])
    return fig


def ip_services_chart(df: pd.DataFrame, country_name: str) -> go.Figure:
    """Line chart of IP service exports, imports, and balance."""
    title = f"Charges for the Use of IP — {country_name} (USD million)"
    if df.empty:
        return _no_data(title)

    fig = _base(title, "USD Million")

    if "exports_usd" in df.columns and df["exports_usd"].notna().any():
        fig.add_trace(go.Scatter(
            x=df["year"], y=df["exports_usd"],
            name="Exports (credits)",
            mode="lines+markers",
            line=dict(color=WTO_COLORS["secondary"], width=2.5),
        ))
    if "imports_usd" in df.columns and df["imports_usd"].notna().any():
        fig.add_trace(go.Scatter(
            x=df["year"], y=df["imports_usd"],
            name="Imports (debits)",
            mode="lines+markers",
            line=dict(color=WTO_COLORS["teal"], width=2.5, dash="dash"),
        ))
    if "balance_usd" in df.columns and df["balance_usd"].notna().any():
        balance_colors = [
            WTO_COLORS["positive"] if (v is not None and v >= 0) else WTO_COLORS["negative"]
            for v in df["balance_usd"].tolist()
        ]
        fig.add_trace(go.Bar(
            x=df["year"], y=df["balance_usd"],
            name="Trade Balance",
            marker_color=balance_colors,
            opacity=0.45,
            yaxis="y2",
        ))
        fig.update_layout(
            yaxis2=dict(
                overlaying="y",
                side="right",
                title="Balance (USD million)",
                showgrid=False,
                zeroline=True,
                zerolinecolor="#CCCCCC",
            )
        )

    return fig


def gi_bar_chart(df: pd.DataFrame, country_name: str) -> go.Figure:
    """Bar chart for Geographical Indications totals."""
    title = f"Geographical Indications — {country_name}"
    if df.empty or "total" not in df.columns:
        return _no_data(title)

    fig = _base(title, "Count")
    fig.add_trace(go.Bar(
        x=df["year"], y=df["total"],
        marker_color=WTO_COLORS["secondary"],
        name="GIs",
    ))
    return fig
