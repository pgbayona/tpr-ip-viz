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
START, END = 2010, 2024


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

# Workbook description
st.markdown(f"""
**Contents of `TPR_IP_{country_code}.xlsx`:**

| Sheet | Contents | Columns |
|-------|----------|---------|
| 1 | Patent Applications | Year · Resident · Non-Resident · Total |
| 2 | Patent Grants | Year · Resident · Non-Resident · Total |
| 3 | Trademark Applications | Year · Resident · Non-Resident · Total |
| 4 | Trademark Registrations | Year · Resident · Non-Resident · Total |
| 5 | Industrial Design Applications | Year · Resident · Non-Resident · Total |
| 6 | Industrial Design Registrations | Year · Resident · Non-Resident · Total |
| 7 | Utility Model Applications | Year · Resident · Non-Resident · Total |
| 8 | Utility Model Grants | Year · Resident · Non-Resident · Total |
| 9 | Geographical Indications | Year · Total |
| 10 | (BOP) Charges for the Use of IP | Year · Imports · Exports |

Coverage: **latest 7 years up to {END}** · Country: **{country_name} ({country_code})**
""")

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
