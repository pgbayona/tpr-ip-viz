"""CountryProfile dataclass and assembly pipeline."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from loguru import logger

# Ensure project root is importable regardless of working directory
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.extract.wipo import WIPOExtractor
from src.extract.wto import WTOExtractor
from src.transform.cleaning import (
    get_alpha2,
    get_alpha3,
    get_country_name,
    fill_missing_years,
)
from src.transform.indicators import (
    resident_share,
    narrative_snippet,
    generate_resident_narrative,
    ip_services_narrative,
    latest_value,
    yoy_delta,
)


# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class CountryProfile:
    country_code: str
    country_name: str
    start_year: int
    end_year: int

    patent_applications:        pd.DataFrame = field(default_factory=pd.DataFrame)
    patent_grants:              pd.DataFrame = field(default_factory=pd.DataFrame)
    trademark_applications:     pd.DataFrame = field(default_factory=pd.DataFrame)
    trademark_registrations:    pd.DataFrame = field(default_factory=pd.DataFrame)
    design_applications:        pd.DataFrame = field(default_factory=pd.DataFrame)
    design_registrations:       pd.DataFrame = field(default_factory=pd.DataFrame)
    utility_model_applications: pd.DataFrame = field(default_factory=pd.DataFrame)
    utility_model_grants:       pd.DataFrame = field(default_factory=pd.DataFrame)
    geographical_indications:   pd.DataFrame = field(default_factory=pd.DataFrame)
    ip_services:                pd.DataFrame = field(default_factory=pd.DataFrame)

    derived: dict = field(default_factory=dict)

    def all_ip_indicators(self) -> dict[str, pd.DataFrame]:
        """Ordered dict of indicator name → DataFrame (WIPO data only)."""
        return {
            "Patent Applications":          self.patent_applications,
            "Patent Grants":                self.patent_grants,
            "Trademark Applications":       self.trademark_applications,
            "Trademark Registrations":      self.trademark_registrations,
            "Industrial Design Applications": self.design_applications,
            "Industrial Design Registrations": self.design_registrations,
            "Utility Model Applications":   self.utility_model_applications,
            "Utility Model Grants":         self.utility_model_grants,
            "Geographical Indications":     self.geographical_indications,
        }


# ── Assembly function ─────────────────────────────────────────────────────────

def assemble_country_profile(
    country_input: str,
    start_year: int = 2010,
    end_year: int = 2024,
) -> CountryProfile:
    """Fetch all data and compute derived metrics for *country_input*.

    *country_input* may be a WTO member name or an ISO alpha-2 code.
    """
    alpha2 = get_alpha2(country_input)
    alpha3 = get_alpha3(country_input)
    name = get_country_name(alpha2 or country_input)

    logger.info(f"=== Assembling profile: {name} ({alpha2} / {alpha3}) ===")

    profile = CountryProfile(
        country_code=alpha2 or country_input.upper()[:2],
        country_name=name,
        start_year=start_year,
        end_year=end_year,
    )

    # ── WIPO + WTO in parallel ────────────────────────────────────────────────
    def _fetch_wipo():
        if not alpha2:
            logger.warning(f"Could not resolve alpha-2 for {country_input!r} — WIPO data skipped")
            return {}
        return WIPOExtractor().get_all_ip_data(alpha2, start_year, end_year)

    def _fetch_wto():
        if not alpha3:
            logger.warning(f"Could not resolve alpha-3 for {country_input!r} — WTO data skipped")
            return pd.DataFrame()
        return WTOExtractor().get_ip_services(alpha3, start_year, end_year)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_wipo = pool.submit(_fetch_wipo)
        f_wto = pool.submit(_fetch_wto)
        raw = f_wipo.result()
        profile.ip_services = f_wto.result()

    profile.patent_applications        = _prep(raw.get("patent_applications"),        start_year, end_year)
    profile.patent_grants              = _prep(raw.get("patent_grants"),              start_year, end_year)
    profile.trademark_applications     = _prep(raw.get("trademark_applications"),     start_year, end_year)
    profile.trademark_registrations    = _prep(raw.get("trademark_registrations"),    start_year, end_year)
    profile.design_applications        = _prep(raw.get("design_applications"),        start_year, end_year)
    profile.design_registrations       = _prep(raw.get("design_registrations"),       start_year, end_year)
    profile.utility_model_applications = _prep(raw.get("utility_model_applications"), start_year, end_year)
    profile.utility_model_grants       = _prep(raw.get("utility_model_grants"),       start_year, end_year)
    profile.geographical_indications   = _prep(raw.get("geographical_indications"),   start_year, end_year)

    # ── Derived metrics ───────────────────────────────────────────────────────
    profile.derived = _compute_derived(name, profile)

    return profile


# ── Helpers ───────────────────────────────────────────────────────────────────

def _prep(df: pd.DataFrame | None, start: int, end: int) -> pd.DataFrame:
    """Fill year gaps and add resident share column."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = fill_missing_years(df, start, end)
    df = resident_share(df)
    return df


def _compute_derived(country_name: str, profile: CountryProfile) -> dict:
    """Build the derived metrics dictionary."""
    overview: dict[str, dict] = {}
    narratives: list[dict] = []

    for ind_name, df in profile.all_ip_indicators().items():
        val, yr = latest_value(df)
        delta = yoy_delta(df)
        overview[ind_name] = {
            "latest_value": val,
            "latest_year": yr,
            "yoy_delta_pct": delta,
        }

        main = narrative_snippet(country_name, ind_name, df)
        narratives.append({"indicator": ind_name, "text": main})

        res_note = generate_resident_narrative(country_name, ind_name, df)
        if res_note:
            narratives.append({"indicator": f"{ind_name} (resident split)", "text": res_note})

    # IP services overview + narratives
    ip = profile.ip_services
    if not ip.empty:
        for col, label in [("exports_usd", "IP Service Exports"), ("imports_usd", "IP Service Imports")]:
            val, yr = latest_value(ip, col)
            delta = yoy_delta(ip, col)
            overview[label] = {"latest_value": val, "latest_year": yr, "yoy_delta_pct": delta}

        text = ip_services_narrative(country_name, ip)
        narratives.append({"indicator": "Charges for the Use of Intellectual Property", "text": text})

    return {"overview": overview, "narratives": narratives}
