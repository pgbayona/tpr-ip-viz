"""TPR IP Viz — Home / country selector page."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Make src/ importable
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Load .env
try:
    from dotenv import load_dotenv
    _env = _ROOT / ".env"
    load_dotenv(_env if _env.exists() else _ROOT / ".env.txt")
except ImportError:
    pass

from src.transform.cleaning import WTO_MEMBERS

st.set_page_config(
    page_title="TPR IP Viz | WTO",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="stSidebar"] { background: #002B45; }
    [data-testid="stSidebar"] * { color: #CCDDEE !important; }
    .hero {
        background: linear-gradient(90deg, #005A8C 0%, #00A9E0 100%);
        padding: 1.6rem 2rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
    }
    .hero h1 { color: white !important; margin: 0; font-size: 2.1rem; }
    .hero p  { color: rgba(255,255,255,0.88); margin: 0.4rem 0 0; font-size: 1.05rem; }
    .info-card {
        background: #EBF5FB;
        border-left: 4px solid #005A8C;
        padding: 0.9rem 1.1rem;
        border-radius: 4px;
        margin-bottom: 1rem;
        font-size: 0.93rem;
    }
    div[data-testid="stButton"] > button {
        background: #005A8C;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.55rem 1.5rem;
        font-size: 1rem;
        width: 100%;
        transition: background 0.2s;
    }
    div[data-testid="stButton"] > button:hover { background: #00A9E0; }
</style>
""", unsafe_allow_html=True)

# ── Hero header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🌐 WTO TPR IP Viz</h1>
  <p>Trade Policy Review — Intellectual Property Statistics Dashboard &amp; Excel Generator</p>
</div>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([3, 2], gap="large")

# ── Country selector ──────────────────────────────────────────────────────────
with col_left:
    st.subheader("Select a WTO Member")

    member_names = sorted(WTO_MEMBERS.keys())

    default_idx = 0
    if "country_name" in st.session_state:
        try:
            default_idx = member_names.index(st.session_state["country_name"])
        except ValueError:
            default_idx = 0

    selected = st.selectbox(
        "WTO Member",
        options=member_names,
        index=default_idx,
        label_visibility="collapsed",
    )

    if st.button("Generate TPR IP Profile", type="primary"):
        st.session_state["country_name"] = selected
        st.session_state["country_code"] = WTO_MEMBERS[selected]

    if "country_name" in st.session_state:
        cname = st.session_state["country_name"]
        ccode = st.session_state["country_code"]
        st.success(
            f"**{cname}** ({ccode}) selected.  "
            "Navigate to **Country Profile** or **Excel Generator** in the sidebar."
        )

# ── Info panel ────────────────────────────────────────────────────────────────
with col_right:
    st.markdown("""
<div class="info-card">
<strong>How to use</strong>
<ol style="margin:0.4rem 0 0; padding-left:1.2rem;">
  <li>Select a WTO Member from the dropdown</li>
  <li>Click <em>Generate TPR IP Profile</em></li>
  <li>Open <strong>Country Profile</strong> for the interactive dashboard</li>
  <li>Open <strong>Excel Generator</strong> to download the workbook</li>
</ol>
</div>

<div class="info-card">
<strong>Data sources</strong>
<ul style="margin:0.4rem 0 0; padding-left:1.2rem;">
  <li>WIPO IP Statistics (patents, trademarks, designs, GIs)</li>
  <li>WTO Timeseries API (IP service trade)</li>
</ul>
<em>Coverage: 2010 – 2024</em>
</div>

<div class="info-card">
<strong>Outputs</strong>
<ul style="margin:0.4rem 0 0; padding-left:1.2rem;">
  <li>Interactive 5-tab IP dashboard</li>
  <li>Downloadable Excel workbook (<code>TPR_IP_&lt;Country&gt;.xlsx</code>)</li>
  <li>Auto-generated TPR narrative snippets</li>
</ul>
</div>
""", unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "WTO Intellectual Property Division · Trade Policy Review Body · "
    "TPR IP Viz v1.0 · Data: WIPO IPSTATS & WTO Timeseries API"
)
