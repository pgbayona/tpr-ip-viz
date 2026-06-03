"""WTO Timeseries API connector for IP services trade data."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pycountry
import requests
from loguru import logger

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_RAW = _ROOT / "data" / "raw"

WTO_API_BASE = "https://api.wto.org/timeseries/v1"

IP_INDICATORS = {
    "ITS_CS_AX6": "IP Service Exports (Charges for use of IP, credits)",
    "ITS_CS_AM6": "IP Service Imports (Charges for use of IP, debits)",
}


_EXTRA_NUMERIC: dict[str, str] = {
    "EP": "918",  # European Union (EPO filings → EU trade reporter)
}


def _alpha3_to_numeric(alpha3: str) -> str:
    """Convert ISO 3166-1 alpha-3 (or sentinel) to WTO numeric reporter code."""
    if alpha3 in _EXTRA_NUMERIC:
        return _EXTRA_NUMERIC[alpha3]
    try:
        return pycountry.countries.get(alpha_3=alpha3).numeric
    except AttributeError:
        return ""


def _api_key() -> str:
    key = os.getenv("WTO_API_KEY", "")
    if not key:
        logger.warning(
            "WTO_API_KEY not set — IP services data will be unavailable. "
            "Add it to your .env file."
        )
    return key


class WTOExtractor:
    """Fetch WTO Timeseries trade-in-services data with disk-level caching."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        raw_dir = Path(os.getenv("DATA_RAW_DIR", str(_DEFAULT_RAW)))
        self.cache_dir = cache_dir or raw_dir / "wto"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._key = _api_key()

    # ── Disk cache helpers ────────────────────────────────────────────────────

    def _cache_path(self, country: str, indicator: str, start: int, end: int) -> Path:
        return self.cache_dir / f"{country}_{indicator}_{start}_{end}.json"

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
        country_alpha3: str,
        indicator: str,
        start: int = 2010,
        end: int = 2025,
    ) -> pd.DataFrame:
        """Return a DataFrame with columns [year, <indicator>] for one WTO indicator."""
        cache_path = self._cache_path(country_alpha3, indicator, start, end)
        cached = self._load(cache_path)

        if cached is not None:
            logger.debug(f"WTO cache hit: {cache_path.name}")
            return self._parse(cached, indicator)

        if not self._key:
            return pd.DataFrame()

        # WTO API requires ISO 3166-1 numeric reporter codes, not alpha-3.
        numeric = _alpha3_to_numeric(country_alpha3)
        if not numeric:
            logger.warning(f"WTO: could not resolve numeric code for {country_alpha3}")
            return pd.DataFrame()

        years = ",".join(str(y) for y in range(start, end + 1))
        params = {
            "i": indicator,
            "r": numeric,
            "p": "000",
            "ps": years,
            "pc": "SH",  # "Charges for the use of intellectual property n.i.e."
            "fmt": "json",
            "mode": "full",
            "lang": 1,
        }
        headers = {
            "Ocp-Apim-Subscription-Key": self._key,
            "Accept": "application/json",
        }

        try:
            logger.info(f"WTO API → indicator={indicator}, reporter={country_alpha3}")
            resp = requests.get(
                f"{WTO_API_BASE}/data",
                params=params,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            self._save(cache_path, data)
            return self._parse(data, indicator)
        except requests.exceptions.HTTPError as exc:
            logger.error(
                f"WTO HTTP error ({indicator}, {country_alpha3}): "
                f"{exc.response.status_code} {exc.response.text[:200]}"
            )
        except requests.exceptions.RequestException as exc:
            logger.error(f"WTO request error ({indicator}, {country_alpha3}): {exc}")
        except Exception as exc:
            logger.error(f"WTO parse error ({indicator}): {exc}")

        return pd.DataFrame()

    # ── Response parser ───────────────────────────────────────────────────────

    def _parse(self, data: dict, indicator: str) -> pd.DataFrame:
        """Normalise WTO Timeseries JSON into a tidy DataFrame."""
        dataset = data.get("Dataset", data.get("data", data.get("Data", [])))
        if not dataset:
            return pd.DataFrame()

        rows = []
        for item in dataset:
            # Year can appear as "Year", "year", or "Period"
            year_raw = item.get("Year", item.get("year", item.get("Period", "")))
            value = item.get("Value", item.get("value", None))
            try:
                year = int(str(year_raw)[:4])
                if value is not None and str(value).strip() not in ("", "null", "None"):
                    rows.append({"year": year, "value": float(value)})
            except (ValueError, TypeError):
                continue

        if not rows:
            return pd.DataFrame()

        df = (
            pd.DataFrame(rows)
            .drop_duplicates("year")
            .sort_values("year")
            .reset_index(drop=True)
        )
        df = df.rename(columns={"value": indicator})
        return df

    # ── Combined IP services fetch ────────────────────────────────────────────

    def get_ip_services(
        self, country_alpha3: str, start: int = 2010, end: int = 2025
    ) -> pd.DataFrame:
        """Return merged exports + imports + balance DataFrame.

        Columns: year, exports_usd, imports_usd, balance_usd
        Values in USD million.
        """
        exports_df = self.fetch_indicator(country_alpha3, "ITS_CS_AX6", start, end)
        imports_df = self.fetch_indicator(country_alpha3, "ITS_CS_AM6", start, end)

        if exports_df.empty and imports_df.empty:
            return pd.DataFrame()

        base = pd.DataFrame({"year": range(start, end + 1)})

        if not exports_df.empty:
            base = base.merge(exports_df, on="year", how="left")
            base = base.rename(columns={"ITS_CS_AX6": "exports_usd"})
        else:
            base["exports_usd"] = float("nan")

        if not imports_df.empty:
            base = base.merge(imports_df, on="year", how="left")
            base = base.rename(columns={"ITS_CS_AM6": "imports_usd"})
        else:
            base["imports_usd"] = float("nan")

        base["balance_usd"] = base["exports_usd"] - base["imports_usd"]
        return base.reset_index(drop=True)
