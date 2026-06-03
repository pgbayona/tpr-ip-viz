"""Smoke tests for the indicators module."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.transform.indicators import (
    cagr,
    growth_pct,
    latest_value,
    yoy_delta,
    resident_share,
    narrative_snippet,
)


def test_cagr_basic():
    result = cagr(100, 200, 5)
    assert result is not None
    assert abs(result - 0.14870) < 0.001


def test_cagr_zero_start():
    assert cagr(0, 200, 5) is None


def test_cagr_negative_years():
    assert cagr(100, 200, 0) is None


def test_growth_pct():
    assert growth_pct(100, 150) == pytest.approx(50.0)


def test_growth_pct_decline():
    assert growth_pct(200, 100) == pytest.approx(-50.0)


def test_growth_pct_zero_start():
    assert growth_pct(0, 100) is None


def test_latest_value():
    df = pd.DataFrame({"year": [2010, 2020, 2022], "total": [100, 200, 300]})
    val, yr = latest_value(df)
    assert val == 300
    assert yr == 2022


def test_latest_value_with_nan():
    df = pd.DataFrame({"year": [2010, 2020, 2022], "total": [100, 200, float("nan")]})
    val, yr = latest_value(df)
    assert val == 200
    assert yr == 2020


def test_yoy_delta():
    df = pd.DataFrame({"year": [2020, 2021], "total": [100.0, 120.0]})
    delta = yoy_delta(df)
    assert delta == pytest.approx(20.0)


def test_resident_share():
    df = pd.DataFrame({
        "year": [2020, 2021],
        "resident": [60.0, 70.0],
        "total": [100.0, 100.0],
    })
    out = resident_share(df)
    assert "resident_share_pct" in out.columns
    assert out["resident_share_pct"].iloc[0] == pytest.approx(60.0)


def test_narrative_snippet_increase():
    df = pd.DataFrame({"year": [2010, 2020], "total": [100.0, 500.0]})
    text = narrative_snippet("Kenya", "Patent Applications", df)
    assert "Kenya" in text
    assert "increased" in text
    assert "100" in text


def test_narrative_snippet_no_data():
    text = narrative_snippet("Kenya", "Patent Applications", pd.DataFrame())
    assert "not available" in text
