"""Excel Generator — download a pre-populated TPR IP workbook."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_CACHE_META = _ROOT / "data" / "last_refreshed.json"


def _cache_status() -> str:
    """Return a human-readable cache freshness string."""
    if not _CACHE_META.exists():
        return "Data cache not yet built. Run `python scripts/prefetch_data.py` first."
    try:
        meta = json.loads(_CACHE_META.read_text())
        ts = datetime.fromisoformat(meta["refreshed_at"])
        age_days = (datetime.now(timezone.utc) - ts).days
        ok = meta.get("success_count", "?")
        total = meta.get("total_countries", "?")
        date_str = ts.strftime("%d %b %Y")
        return (
            f"Cache last refreshed: **{date_str}** ({age_days} days ago) · "
            f"{ok}/{total} countries · years {meta.get('start_year')}–{meta.get('end_year')}"
        )
    except Exception:
        return "Cache metadata unreadable."

try:
    from dotenv import load_dotenv
    _env = _ROOT / ".env"
    load_dotenv(_env if _env.exists() else _ROOT / ".env.txt")
except ImportError:
    pass

from src.viz.profile import assemble_country_profile, CountryProfile
from src.excel.template_writer import write_country_workbook


# ── Guard ─────────────────────────────────────────────────────────────────────
if "country_name" not in st.session_state:
    st.warning(
        "No country selected. Please go to the **Home** page and click "
        "*Generate TPR IP Profile* first."
    )
    st.stop()

country_name = st.session_state["country_name"]
country_code = st.session_state.get("country_code", "XX")
TEMPLATE_PATH = _ROOT / "templates" / "TPR_IP_Template.xlsx"
START, END = 2004, 2024


@st.cache_data(ttl=3600, show_spinner=False)
def _load(name: str, s: int, e: int) -> CountryProfile:
    return assemble_country_profile(name, s, e)


# ── Page header ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="page-hero">
  <h2>Excel Generator &mdash; {country_name}</h2>
  <p>Generate and download a pre-populated TPR IP workbook</p>
</div>
""", unsafe_allow_html=True)

# Template status banner
if TEMPLATE_PATH.exists():
    st.success(f"Template found: `templates/TPR_IP_Template.xlsx`")
else:
    st.warning(
        "Template not found at `templates/TPR_IP_Template.xlsx`. "
        "Drop your template there to use chart placeholders.  "
        "A plain data workbook will be generated until then."
    )

# Cache freshness banner
st.info(_cache_status())

# ── Summary sheet preview ─────────────────────────────────────────────────────
from datetime import date as _date
import pandas as _pd
from src.excel.template_writer import SHEET_CONFIG, _SUMMARY_ROW_MAP

_pulled   = _date.today().strftime("%d/%m/%Y")
_wipo_src = f"WIPO IP Statistics Data Center. Viewed at: https://www3.wipo.int/ipstats ({_pulled})."
_wto_src  = f"WTO Stats Portal. Viewed at: https://stats.wto.org/ ({_pulled})."

# Load profile (cached) and compute per-indicator actual year ranges
with st.spinner("Computing data coverage…"):
    _preview_profile = _load(country_name, START, END)

_DISPLAY_FROM = 2010
_sheet_year_range: dict[str, str] = {}
for attr, hint, _ in SHEET_CONFIG:
    _df = getattr(_preview_profile, attr, _pd.DataFrame())
    if not isinstance(_df, _pd.DataFrame) or _df.empty or "year" not in _df.columns:
        _sheet_year_range[hint] = "N/A"
        continue
    _val_cols = [c for c in _df.columns if c != "year"]
    if not _val_cols:
        _sheet_year_range[hint] = "N/A"
        continue
    _df = _df[_df["year"] >= _DISPLAY_FROM]
    _df = _df[_df[_val_cols].notna().any(axis=1)]
    _df = _df.sort_values("year").tail(7)
    if _df.empty:
        _sheet_year_range[hint] = "N/A"
    else:
        _sheet_year_range[hint] = f"{int(_df['year'].min())}–{int(_df['year'].max())}"

_rows_html = ""
for i, ((_, label, src_type), (_, hint, _)) in enumerate(
    zip(_SUMMARY_ROW_MAP, SHEET_CONFIG), start=1
):
    yr        = _sheet_year_range.get(hint, "N/A")
    title_cell  = f"{country_name} {label}: {yr}" if yr != "N/A" else f"No data ({_DISPLAY_FROM}–{END})"
    source_cell = _wipo_src if src_type == "WIPO" else _wto_src
    badge_color = "#004C97" if src_type == "WIPO" else "#007B8A"
    row_bg      = "#F4F8FC" if i % 2 == 0 else "#FFFFFF"
    na_style    = "color:#AAA;font-style:italic;" if yr == "N/A" else "font-weight:500;color:#002F5F;"
    _rows_html += f"""
    <tr style="background:{row_bg};">
      <td style="padding:6px 10px;color:#555;font-size:0.82rem;width:28px;text-align:center;">{i}</td>
      <td style="padding:6px 12px;{na_style}">{title_cell}</td>
      <td style="padding:6px 12px;color:#555;font-size:0.8rem;font-style:italic;">{source_cell}</td>
      <td style="padding:6px 10px;text-align:center;">
        <span style="background:{badge_color};color:white;font-size:0.72rem;padding:2px 7px;border-radius:3px;font-weight:600;">{src_type}</span>
      </td>
    </tr>"""

st.markdown(f"""
<div style="margin-bottom:1.2rem;">
  <div style="font-size:0.78rem;font-weight:700;letter-spacing:0.08em;color:#7F8C8D;text-transform:uppercase;margin-bottom:0.5rem;">
    Summary Sheet Preview &nbsp;·&nbsp; {country_name} ({country_code})
  </div>
  <table style="width:100%;border-collapse:collapse;border:1px solid #D0DEF0;border-radius:6px;overflow:hidden;font-family:Arial,sans-serif;font-size:0.88rem;">
    <thead>
      <tr style="background:#002F5F;color:white;">
        <th style="padding:7px 10px;width:28px;">#</th>
        <th style="padding:7px 12px;text-align:left;">Chart / Table Title</th>
        <th style="padding:7px 12px;text-align:left;">Source Citation</th>
        <th style="padding:7px 10px;width:52px;">Source</th>
      </tr>
    </thead>
    <tbody>{_rows_html}</tbody>
  </table>
  <div style="font-size:0.77rem;color:#888;margin-top:0.4rem;">
    Year ranges reflect actual WIPO/WTO data availability per indicator (latest 7 years with data).
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

if st.button("Generate Excel Workbook", type="primary"):
    progress = st.progress(0, text="Fetching IP data…")

    try:
        with st.spinner(f"Loading data for {country_name}…"):
            profile = _load(country_name, START, END)
        progress.progress(55, text="Writing Excel workbook…")

        buf = write_country_workbook(
            profile,
            template_path=TEMPLATE_PATH if TEMPLATE_PATH.exists() else None,
        )
        progress.progress(100, text="Ready!")

        filename = f"TPR_IP_{country_code}.xlsx"
        st.download_button(
            label=f"⬇️ Download {filename}",
            data=buf,
            file_name=filename,
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
        )
        st.success(
            f"**{filename}** is ready. Click the button above to download.  "
            "Open in Excel — charts will refresh automatically from the data ranges."
        )

    except Exception as exc:
        st.error(f"Failed to generate workbook: {exc}")
        with st.expander("Error details"):
            st.exception(exc)
