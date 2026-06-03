"""Derived metrics and TPR narrative generators."""
from __future__ import annotations

import pandas as pd
from loguru import logger


# ── Statistical helpers ───────────────────────────────────────────────────────

def cagr(start_val: float, end_val: float, n_years: int) -> float | None:
    """Compound Annual Growth Rate.  Returns None when inputs are invalid."""
    if n_years <= 0 or not start_val or start_val <= 0 or end_val is None:
        return None
    try:
        return (end_val / start_val) ** (1.0 / n_years) - 1.0
    except (ZeroDivisionError, ValueError):
        return None


def growth_pct(start_val: float | None, end_val: float | None) -> float | None:
    """Simple percentage change.  Returns None on invalid inputs."""
    if start_val is None or end_val is None or start_val == 0:
        return None
    return (end_val - start_val) / start_val * 100.0


def latest_value(
    df: pd.DataFrame, value_col: str = "total"
) -> tuple[float | None, int | None]:
    """Return (value, year) of the most recent non-null row."""
    if df.empty or value_col not in df.columns:
        return None, None
    valid = df[df[value_col].notna()].sort_values("year", ascending=False)
    if valid.empty:
        return None, None
    row = valid.iloc[0]
    return float(row[value_col]), int(row["year"])


def yoy_delta(df: pd.DataFrame, value_col: str = "total") -> float | None:
    """Year-on-year percentage change between the two most recent data points."""
    if df.empty or value_col not in df.columns:
        return None
    valid = df[df[value_col].notna()].sort_values("year", ascending=False)
    if len(valid) < 2:
        return None
    current = float(valid.iloc[0][value_col])
    previous = float(valid.iloc[1][value_col])
    if previous == 0:
        return None
    return (current - previous) / previous * 100.0


# ── DataFrame enrichment ─────────────────────────────────────────────────────

def resident_share(df: pd.DataFrame) -> pd.DataFrame:
    """Add *resident_share_pct* column (resident / total × 100)."""
    if df.empty or "resident" not in df.columns or "total" not in df.columns:
        return df
    out = df.copy()
    with pd.option_context("mode.use_inf_as_na", True):
        out["resident_share_pct"] = (
            out["resident"] / out["total"] * 100.0
        ).where(out["total"] > 0).round(1)
    return out


def grant_rate(
    apps_df: pd.DataFrame, grants_df: pd.DataFrame
) -> pd.DataFrame | None:
    """grants / applications × 100 by year."""
    if apps_df.empty or grants_df.empty:
        return None
    if "total" not in apps_df.columns or "total" not in grants_df.columns:
        return None
    merged = apps_df[["year", "total"]].merge(
        grants_df[["year", "total"]], on="year", suffixes=("_apps", "_grants")
    )
    mask = merged["total_apps"] > 0
    merged.loc[mask, "grant_rate_pct"] = (
        merged.loc[mask, "total_grants"] / merged.loc[mask, "total_apps"] * 100.0
    ).round(1)
    return merged[["year", "grant_rate_pct"]]


# ── Narrative generation ──────────────────────────────────────────────────────

def _fmt(val: float) -> str:
    """Format a number for narrative text."""
    if val >= 1_000_000:
        return f"{val / 1_000_000:.2f} million"
    if val >= 1_000:
        return f"{val:,.0f}"
    return f"{val:.1f}"


def narrative_snippet(
    country_name: str,
    indicator_name: str,
    df: pd.DataFrame,
    value_col: str = "total",
) -> str:
    """Generate a ready-to-paste TPR sentence for one indicator."""
    if df.empty or value_col not in df.columns:
        return f"Data on {indicator_name} is not available for {country_name}."

    valid = df[df[value_col].notna()].copy()
    if valid.empty:
        return f"Data on {indicator_name} is not available for {country_name}."

    start_year = int(valid["year"].min())
    end_year = int(valid["year"].max())

    def _val(yr: int) -> float | None:
        row = valid[valid["year"] == yr]
        if row.empty:
            return None
        v = row[value_col].iloc[0]
        return float(v) if not pd.isna(v) else None

    sv = _val(start_year)
    ev = _val(end_year)

    if sv is None or ev is None:
        return (
            f"Partial data on {indicator_name} is available for {country_name} "
            f"({start_year}–{end_year})."
        )

    pct = growth_pct(sv, ev)
    n_yrs = end_year - start_year
    rate = cagr(sv, ev, n_yrs)

    if abs(ev - sv) < 0.01:
        direction = "remained stable"
    elif ev > sv:
        direction = "increased"
    else:
        direction = "decreased"

    sentence = (
        f"{indicator_name} in {country_name} {direction} from "
        f"{_fmt(sv)} in {start_year} to {_fmt(ev)} in {end_year}"
    )

    if pct is not None and direction != "remained stable":
        change_word = "growth" if direction == "increased" else "a decline"
        sentence += f", representing {change_word} of {abs(pct):.1f}%"
        if rate is not None:
            sentence += f" (CAGR: {abs(rate) * 100:.1f}%)"

    return sentence + "."


def generate_resident_narrative(
    country_name: str,
    indicator_name: str,
    df: pd.DataFrame,
) -> str | None:
    """Supplemental sentence about resident vs. non-resident split."""
    if df.empty or "resident_share_pct" not in df.columns:
        return None
    valid = df[df["resident_share_pct"].notna()].sort_values("year")
    if valid.empty:
        return None
    latest = valid.iloc[-1]
    yr = int(latest["year"])
    share = float(latest["resident_share_pct"])
    dominant = "resident" if share >= 50 else "non-resident"
    other_share = 100.0 - share
    other_pct = share if dominant == "non-resident" else other_share
    if dominant == "resident":
        return (
            f"In {yr}, resident applicants accounted for {share:.1f}% of "
            f"{indicator_name.lower()} in {country_name}."
        )
    return (
        f"{indicator_name} in {country_name} remains dominated by non-resident applicants, "
        f"accounting for {other_pct:.1f}% of filings in {yr}."
    )
