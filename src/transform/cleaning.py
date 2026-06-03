"""Country code helpers and WTO membership list."""
from __future__ import annotations

import pycountry
import pandas as pd
from loguru import logger

# ── WTO Members: display name → ISO 3166-1 alpha-2 ──────────────────────────
# Source: WTO membership list (164 members as of 2024)
WTO_MEMBERS: dict[str, str] = {
    "Afghanistan": "AF",
    "Albania": "AL",
    "Angola": "AO",
    "Antigua and Barbuda": "AG",
    "Argentina": "AR",
    "Armenia": "AM",
    "Australia": "AU",
    "Austria": "AT",
    "Bahrain, Kingdom of": "BH",
    "Bangladesh": "BD",
    "Barbados": "BB",
    "Belgium": "BE",
    "Belize": "BZ",
    "Benin": "BJ",
    "Bolivia, Plurinational State of": "BO",
    "Botswana": "BW",
    "Brazil": "BR",
    "Brunei Darussalam": "BN",
    "Burkina Faso": "BF",
    "Burundi": "BI",
    "Cabo Verde": "CV",
    "Cambodia": "KH",
    "Cameroon": "CM",
    "Canada": "CA",
    "Central African Republic": "CF",
    "Chad": "TD",
    "Chile": "CL",
    "China": "CN",
    "Colombia": "CO",
    "Congo": "CG",
    "Costa Rica": "CR",
    "Côte d'Ivoire": "CI",
    "Croatia": "HR",
    "Cuba": "CU",
    "Cyprus": "CY",
    "Czech Republic": "CZ",
    "Democratic Republic of the Congo": "CD",
    "Denmark": "DK",
    "Djibouti": "DJ",
    "Dominica": "DM",
    "Dominican Republic": "DO",
    "Ecuador": "EC",
    "Egypt": "EG",
    "El Salvador": "SV",
    "Estonia": "EE",
    "Eswatini": "SZ",
    "Fiji": "FJ",
    "Finland": "FI",
    "France": "FR",
    "Gabon": "GA",
    "Gambia": "GM",
    "Georgia": "GE",
    "Germany": "DE",
    "Ghana": "GH",
    "Greece": "GR",
    "Grenada": "GD",
    "Guatemala": "GT",
    "Guinea": "GN",
    "Guinea-Bissau": "GW",
    "Guyana": "GY",
    "Haiti": "HT",
    "Honduras": "HN",
    "Hong Kong, China": "HK",
    "Hungary": "HU",
    "Iceland": "IS",
    "India": "IN",
    "Indonesia": "ID",
    "Ireland": "IE",
    "Israel": "IL",
    "Italy": "IT",
    "Jamaica": "JM",
    "Japan": "JP",
    "Jordan": "JO",
    "Kazakhstan": "KZ",
    "Kenya": "KE",
    "Korea, Republic of": "KR",
    "Kuwait, the State of": "KW",
    "Kyrgyz Republic": "KG",
    "Lao People's Democratic Republic": "LA",
    "Latvia": "LV",
    "Lesotho": "LS",
    "Liberia": "LR",
    "Liechtenstein": "LI",
    "Lithuania": "LT",
    "Luxembourg": "LU",
    "Macao, China": "MO",
    "Madagascar": "MG",
    "Malawi": "MW",
    "Malaysia": "MY",
    "Maldives": "MV",
    "Mali": "ML",
    "Malta": "MT",
    "Mauritania": "MR",
    "Mauritius": "MU",
    "Mexico": "MX",
    "Moldova, Republic of": "MD",
    "Mongolia": "MN",
    "Montenegro": "ME",
    "Morocco": "MA",
    "Mozambique": "MZ",
    "Myanmar": "MM",
    "Namibia": "NA",
    "Nepal": "NP",
    "Netherlands": "NL",
    "New Zealand": "NZ",
    "Nicaragua": "NI",
    "Niger": "NE",
    "Nigeria": "NG",
    "North Macedonia": "MK",
    "Norway": "NO",
    "Oman": "OM",
    "Pakistan": "PK",
    "Panama": "PA",
    "Papua New Guinea": "PG",
    "Paraguay": "PY",
    "Peru": "PE",
    "Philippines": "PH",
    "Poland": "PL",
    "Portugal": "PT",
    "Qatar": "QA",
    "Romania": "RO",
    "Russian Federation": "RU",
    "Rwanda": "RW",
    "Saint Kitts and Nevis": "KN",
    "Saint Lucia": "LC",
    "Saint Vincent and the Grenadines": "VC",
    "Samoa": "WS",
    "Saudi Arabia, Kingdom of": "SA",
    "Senegal": "SN",
    "Seychelles": "SC",
    "Sierra Leone": "SL",
    "Singapore": "SG",
    "Slovak Republic": "SK",
    "Slovenia": "SI",
    "Solomon Islands": "SB",
    "South Africa": "ZA",
    "Spain": "ES",
    "Sri Lanka": "LK",
    "Suriname": "SR",
    "Sweden": "SE",
    "Switzerland": "CH",
    "Chinese Taipei": "TW",
    "Tajikistan": "TJ",
    "Tanzania": "TZ",
    "Thailand": "TH",
    "Togo": "TG",
    "Tonga": "TO",
    "Trinidad and Tobago": "TT",
    "Tunisia": "TN",
    "Türkiye": "TR",
    "Uganda": "UG",
    "Ukraine": "UA",
    "United Arab Emirates": "AE",
    "United Kingdom": "GB",
    "United States of America": "US",
    "Uruguay": "UY",
    "Vanuatu": "VU",
    "Venezuela, Bolivarian Republic of": "VE",
    "Viet Nam": "VN",
    "Yemen": "YE",
    "Zambia": "ZM",
    "Zimbabwe": "ZW",
}

# Reverse lookup: alpha-2 → display name
_CODE_TO_NAME: dict[str, str] = {v: k for k, v in WTO_MEMBERS.items()}


# ── Country code resolution ───────────────────────────────────────────────────

def get_alpha2(country_input: str) -> str | None:
    """Resolve a country name or alpha-2/alpha-3 code to ISO alpha-2."""
    s = country_input.strip()

    if len(s) == 2:
        return s.upper()

    # Direct WTO name match (case-insensitive)
    s_lower = s.lower()
    for name, code in WTO_MEMBERS.items():
        if name.lower() == s_lower:
            return code

    # Partial match on WTO names
    for name, code in WTO_MEMBERS.items():
        if s_lower in name.lower():
            return code

    # pycountry fallback
    try:
        c = pycountry.countries.lookup(s)
        return c.alpha_2
    except LookupError:
        pass

    logger.warning(f"Could not resolve country alpha-2 for: {s!r}")
    return None


def get_alpha3(country_input: str) -> str | None:
    """Resolve a country name or code to ISO alpha-3."""
    s = country_input.strip()

    if len(s) == 3 and s.isupper():
        # Could already be alpha-3
        c = pycountry.countries.get(alpha_3=s.upper())
        if c:
            return c.alpha_3

    alpha2 = get_alpha2(s)
    if alpha2 is None:
        return None

    try:
        c = pycountry.countries.get(alpha_2=alpha2)
        if c:
            return c.alpha_3
    except Exception:
        pass

    logger.warning(f"Could not resolve alpha-3 for: {s!r}")
    return None


def get_country_name(country_code: str) -> str:
    """Return the WTO display name (or pycountry fallback) for an alpha-2 code."""
    code = country_code.strip().upper()
    if code in _CODE_TO_NAME:
        return _CODE_TO_NAME[code]
    try:
        c = pycountry.countries.get(alpha_2=code)
        if c:
            return c.name
    except Exception:
        pass
    return code


# ── DataFrame helpers ────────────────────────────────────────────────────────

def fill_missing_years(df: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    """Ensure a year column covering [start, end] exists; fill gaps with NaN."""
    if df.empty:
        return pd.DataFrame({"year": range(start, end + 1)})
    all_years = pd.DataFrame({"year": list(range(start, end + 1))})
    return all_years.merge(df, on="year", how="left").reset_index(drop=True)


def standardize(
    df: pd.DataFrame,
    country: str,
    indicator: str,
    source: str,
) -> pd.DataFrame:
    """Attach metadata columns to a tidy DataFrame."""
    if df.empty:
        return df
    out = df.copy()
    out["country"] = country
    out["indicator"] = indicator
    out["source"] = source
    return out
