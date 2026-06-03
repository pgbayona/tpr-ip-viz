"""Excel Generator — download a pre-populated TPR IP workbook."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    _env = _ROOT / ".env"
    load_dotenv(_env if _env.exists() else _ROOT / ".env.txt")
except ImportError:
    pass

from src.viz.profile import assemble_country_profile, CountryProfile
from src.excel.template_writer import write_country_workbook

st.set_page_config(
    page_title="Excel Generator | TPR IP Viz",
    page_icon="📥",
    layout="wide",
)

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
<div style="background:linear-gradient(90deg,#005A8C,#00A9E0);
            padding:1rem 1.5rem;border-radius:8px;margin-bottom:1.5rem;">
  <h2 style="color:white;margin:0;">📥 Excel Generator — {country_name}</h2>
  <p style="color:rgba(255,255,255,0.85);margin:0;">
    Generate and download a pre-populated TPR IP workbook
  </p>
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
| 10 | IP Service Exports | Year · USD million |
| 11 | IP Service Imports | Year · USD million |

Coverage: **{START}–{END}** · Country: **{country_name} ({country_code})**
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
