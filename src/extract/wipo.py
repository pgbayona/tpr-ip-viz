"""WIPO IPSTATS REST API connector with disk caching."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
from loguru import logger

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_RAW = _ROOT / "data" / "raw"

WIPO_API_BASE = os.getenv("WIPO_API_BASE", "https://www.wipo.int/ipstats/api/data")

INDICATORS: dict[str, dict] = {
    "patent_applications": {
        "code": 10,
        "name": "Patent Applications",
        "has_origin": True,
    },
    "patent_grants": {
        "code": 23,
        "name": "Patent Grants",
        "has_origin": True,
    },
    "trademark_applications": {
        "code": 30,
        "name": "Trademark Applications",
        "has_origin": True,
    },
    "trademark_registrations": {
        "code": 47,
        "name": "Trademark Registrations",
        "has_origin": True,
    },
    "design_applications": {
        "code": 50,
        "name": "Industrial Design Applications",
        "has_origin": True,
    },
    "design_registrations": {
        "code": 66,
        "name": "Industrial Design Registrations",
        "has_origin": True,
    },
    "utility_model_applications": {
        "code": 70,
        "name": "Utility Model Applications",
        "has_origin": True,
    },
    "utility_model_grants": {
        "code": 75,
        "name": "Utility Model Grants",
        "has_origin": True,
    },
    "geographical_indications": {
        "code": 503,
        "name": "Geographical Indications",
        "has_origin": False,
    },
}

_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "TPR-IP-Viz/1.0 (WTO Intellectual Property Division)",
}


class WIPOExtractor:
    """Fetch WIPO IP statistics for a country with disk-level caching."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        raw_dir = Path(os.getenv("DATA_RAW_DIR", str(_DEFAULT_RAW)))
        self.cache_dir = cache_dir or raw_dir / "wipo"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Disk cache helpers ────────────────────────────────────────────────────

    def _cache_path(self, country: str, code: int, start: int, end: int) -> Path:
        return self.cache_dir / f"{country}_{code}_{start}_{end}.json"

    def _load(self, path: Path) -> dict | list | None:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                return None
        return None

    def _save(self, path: Path, data: dict | list) -> None:
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        except Exception as exc:
            logger.warning(f"Cache write failed ({path.name}): {exc}")

    # ── Core fetch ────────────────────────────────────────────────────────────

    def fetch_indicator(
        self,
        country: str,
        indicator_code: int,
        start: int = 2010,
        end: int = 2024,
        breakdown: bool = True,
    ) -> pd.DataFrame:
        """Return a DataFrame for one WIPO indicator.

        Columns (breakdown=True):  year, resident, non_resident, total
        Columns (breakdown=False): year, total
        """
        cache_path = self._cache_path(country, indicator_code, start, end)
        cached = self._load(cache_path)

        if cached is not None:
            logger.debug(f"WIPO cache hit: {cache_path.name}")
            return self._parse(cached, indicator_code)

        params: dict[str, object] = {
            "indicator": indicator_code,
            "geo": country,
            "start": start,
            "end": end,
        }
        if breakdown:
            params["breakdown"] = "ORIGIN"

        try:
            logger.info(f"WIPO API → indicator={indicator_code}, geo={country}")
            resp = requests.get(
                WIPO_API_BASE, params=params, headers=_HEADERS, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            self._save(cache_path, data)
            return self._parse(data, indicator_code)
        except requests.exceptions.HTTPError as exc:
            logger.error(
                f"WIPO HTTP error (ind={indicator_code}, geo={country}): "
                f"{exc.response.status_code} {exc.response.text[:200]}"
            )
        except requests.exceptions.RequestException as exc:
            logger.error(f"WIPO request error (ind={indicator_code}, geo={country}): {exc}")
        except Exception as exc:
            logger.error(f"WIPO parse error (ind={indicator_code}): {exc}")

        return pd.DataFrame()

    # ── Response parser ───────────────────────────────────────────────────────

    def _parse(self, data: dict | list, indicator_code: int) -> pd.DataFrame:
        """Normalise any WIPO response shape into a tidy DataFrame."""
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = data.get(
                "data",
                data.get("Dataset", data.get("records", data.get("results", []))),
            )
            if isinstance(rows, dict):
                rows = [rows]
        else:
            return pd.DataFrame()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df.columns = [str(c).lower().strip() for c in df.columns]

        # ── year column ──
        year_col = next(
            (c for c in df.columns if c in ("year", "yr", "periodfrom", "period", "date")),
            None,
        )
        if year_col is None:
            logger.warning(f"WIPO ind={indicator_code}: no year column in {list(df.columns)}")
            return pd.DataFrame()
        df = df.rename(columns={year_col: "year"})
        df["year"] = pd.to_numeric(df["year"].astype(str).str[:4], errors="coerce")
        df = df.dropna(subset=["year"])
        df["year"] = df["year"].astype(int)

        # ── value column ──
        value_col = next(
            (c for c in df.columns if c in ("value", "val", "count", "total", "number")),
            None,
        )
        if value_col is None:
            logger.warning(f"WIPO ind={indicator_code}: no value column in {list(df.columns)}")
            return pd.DataFrame()
        df["value"] = pd.to_numeric(df[value_col], errors="coerce")

        # ── origin breakdown ──
        origin_col = next(
            (
                c
                for c in df.columns
                if c in ("origin", "breakdown", "applicant_origin", "origin_code", "type")
            ),
            None,
        )

        if origin_col:
            df["origin"] = (
                df[origin_col]
                .astype(str)
                .str.upper()
                .str.strip()
                .replace(
                    {
                        "NON_RESIDENT": "NONRESIDENT",
                        "NON-RESIDENT": "NONRESIDENT",
                        "FOREIGN": "NONRESIDENT",
                        "NR": "NONRESIDENT",
                        "R": "RESIDENT",
                        "RES": "RESIDENT",
                    }
                )
            )
            pivot = (
                df.pivot_table(
                    index="year", columns="origin", values="value", aggfunc="sum"
                )
                .reset_index()
            )
            pivot.columns.name = None

            rename: dict[str, str] = {}
            for col in pivot.columns:
                u = str(col).upper()
                if u == "RESIDENT":
                    rename[col] = "resident"
                elif u in ("NONRESIDENT", "NON_RESIDENT"):
                    rename[col] = "non_resident"
                elif u in ("TOTAL", "ALL"):
                    rename[col] = "total"
            pivot = pivot.rename(columns=rename)

            if "total" not in pivot.columns:
                res = pivot.get("resident", pd.Series(dtype=float))
                nr = pivot.get("non_resident", pd.Series(dtype=float))
                pivot["total"] = res.fillna(0) + nr.fillna(0)

            keep = ["year"] + [
                c for c in ("resident", "non_resident", "total") if c in pivot.columns
            ]
            return pivot[keep].sort_values("year").reset_index(drop=True)

        # No origin breakdown — just total
        out = df[["year", "value"]].copy().rename(columns={"value": "total"})
        return out.sort_values("year").reset_index(drop=True)

    # ── Bulk fetch ────────────────────────────────────────────────────────────

    def get_all_ip_data(
        self, country: str, start: int = 2010, end: int = 2024
    ) -> dict[str, pd.DataFrame]:
        """Fetch all 9 WIPO indicators for *country* (ISO alpha-2)."""
        result: dict[str, pd.DataFrame] = {}
        for key, meta in INDICATORS.items():
            logger.info(f"Fetching {meta['name']} for {country}…")
            result[key] = self.fetch_indicator(
                country,
                meta["code"],
                start,
                end,
                breakdown=meta["has_origin"],
            )
            time.sleep(0.4)  # polite delay
        return result
