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

_WIPO_BASE = "https://api.ipstatsdc.deda.prd.web1.wipo.int/api/v1/public/ips-search"
_TABLE_RESULT = f"{_WIPO_BASE}/table-result"

# Both headers are required by the server.
_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "en",
    "User-Agent": "TPR-IP-Viz/1.0 (WTO Intellectual Property Division)",
}

INDICATORS: dict[str, dict] = {
    "patent_applications": {
        "tab": "patent",
        "id": 10,
        "name": "Patent Applications",
        "has_origin": True,
    },
    "patent_grants": {
        "tab": "patent",
        "id": 23,
        "name": "Patent Grants",
        "has_origin": True,
    },
    "trademark_applications": {
        "tab": "trademark",
        "id": 30,
        "name": "Trademark Applications",
        "has_origin": True,
    },
    "trademark_registrations": {
        "tab": "trademark",
        "id": 47,
        "name": "Trademark Registrations",
        "has_origin": True,
    },
    "design_applications": {
        "tab": "industrial",
        "id": 50,
        "name": "Industrial Design Applications",
        "has_origin": True,
    },
    "design_registrations": {
        "tab": "industrial",
        "id": 66,
        "name": "Industrial Design Registrations",
        "has_origin": True,
    },
    "utility_model_applications": {
        "tab": "utility",
        "id": 70,
        "name": "Utility Model Applications",
        "has_origin": True,
    },
    "utility_model_grants": {
        "tab": "utility",
        "id": 75,
        "name": "Utility Model Grants",
        "has_origin": True,
    },
    "geographical_indications": {
        "tab": "geographical",
        "id": 503,
        "name": "Geographical Indications",
        "has_origin": False,
    },
}


class WIPOExtractor:
    """Fetch WIPO IP statistics for a country with disk-level caching."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        raw_dir = Path(os.getenv("DATA_RAW_DIR", str(_DEFAULT_RAW)))
        self.cache_dir = cache_dir or raw_dir / "wipo"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Disk cache helpers ────────────────────────────────────────────────────

    def _cache_path(self, country: str, indicator_id: int, start: int, end: int) -> Path:
        return self.cache_dir / f"{country}_{indicator_id}_{start}_{end}.json"

    def _load(self, path: Path) -> dict | None:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                return None
        return None

    def _save(self, path: Path, data: dict) -> None:
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        except Exception as exc:
            logger.warning(f"Cache write failed ({path.name}): {exc}")

    # ── Core fetch ────────────────────────────────────────────────────────────

    def fetch_indicator(
        self,
        country: str,
        tab: str,
        indicator_id: int,
        has_origin: bool,
        start: int = 2010,
        end: int = 2024,
    ) -> pd.DataFrame:
        """Fetch one WIPO indicator for *country* (ISO alpha-2).

        Columns (has_origin=True):  year, resident, non_resident, total
        Columns (has_origin=False): year, total
        """
        cache_path = self._cache_path(country, indicator_id, start, end)
        cached = self._load(cache_path)

        if cached is not None:
            logger.debug(f"WIPO cache hit: {cache_path.name}")
            return self._parse(cached, has_origin)

        params = {
            "type": "IPS",
            "selectedTab": tab,
            "indicator": indicator_id,
            "reportType": "11",
            "fromYear": start,
            "toYear": end,
            "ipsOffSelValues": country,
        }

        try:
            logger.info(f"WIPO API → indicator={indicator_id}, geo={country}")
            resp = requests.get(
                _TABLE_RESULT, params=params, headers=_HEADERS, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            self._save(cache_path, data)
            return self._parse(data, has_origin)
        except requests.exceptions.HTTPError as exc:
            logger.error(
                f"WIPO HTTP error (ind={indicator_id}, geo={country}): "
                f"{exc.response.status_code} {exc.response.text[:200]}"
            )
        except requests.exceptions.RequestException as exc:
            logger.error(f"WIPO request error (ind={indicator_id}, geo={country}): {exc}")
        except Exception as exc:
            logger.error(f"WIPO parse error (ind={indicator_id}): {exc}")

        return pd.DataFrame()

    # ── Response parser ───────────────────────────────────────────────────────

    def _parse(self, data: dict, has_origin: bool) -> pd.DataFrame:
        """Parse the /table-result response into a tidy DataFrame.

        The API returns each year value as a comma-separated string where one
        value is the sum of the others (= total). For origin indicators the two
        breakdown values are resident and non-resident filing counts.
        """
        records = data.get("records", [])
        columns_meta = data.get("columns", [])

        if not records:
            return pd.DataFrame()

        year_cols = [
            col["code"]
            for col in columns_meta
            if col.get("type") == "number"
        ]
        record = records[0]

        rows = []
        for yr_str in year_cols:
            raw = record.get(yr_str)
            if raw is None:
                continue

            try:
                parts = [float(v.strip()) for v in str(raw).split(",") if v.strip()]
            except ValueError:
                continue

            year = int(yr_str)

            if len(parts) == 3 and has_origin:
                a, b, c = parts
                # Identify which value is the total (= sum of the other two).
                if abs(a - b - c) < 1:
                    total, p, q = a, b, c
                elif abs(b - a - c) < 1:
                    total, p, q = b, a, c
                else:
                    total, p, q = c, a, b
                resident = max(p, q)
                non_resident = min(p, q)
                rows.append(
                    {
                        "year": year,
                        "resident": resident,
                        "non_resident": non_resident,
                        "total": total,
                    }
                )
            else:
                # GI or single-value: sum all parts for total.
                rows.append({"year": year, "total": sum(parts)})

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["year"] = df["year"].astype(int)
        for col in df.columns:
            if col != "year":
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.sort_values("year").reset_index(drop=True)

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
                meta["tab"],
                meta["id"],
                meta["has_origin"],
                start,
                end,
            )
            time.sleep(0.4)
        return result
