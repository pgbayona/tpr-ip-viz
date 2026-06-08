"""TPR IP Viz — page router."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    _env = _ROOT / ".env"
    load_dotenv(_env if _env.exists() else _ROOT / ".env.txt")
except ImportError:
    pass

st.set_page_config(
    page_title="TPR IP Viz | WTO",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Discourage search engine indexing.
# Not a security measure — the password gate handles access control.
st.markdown(
    '<meta name="robots" content="noindex, nofollow">',
    unsafe_allow_html=True,
)

# WTO logo — drop wto_logo.png into app/static/ to enable

# Global CSS shared across all pages
st.markdown("""
<style>
    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: #001E35;
        border-right: 1px solid #003055;
    }
    [data-testid="stSidebar"] * { color: #B8D4EA !important; }
    [data-testid="stSidebar"] a:hover * { color: #FFFFFF !important; }

    /* ── Hero banner (shared) ── */
    .hero, .page-hero {
        background: linear-gradient(100deg, #002F5F 0%, #004C97 60%, #0062B8 100%);
        border-radius: 10px;
        border-bottom: 3px solid rgba(255,255,255,0.35);
        box-shadow: 0 2px 12px rgba(0,40,100,0.22);
        margin-bottom: 1.6rem;
    }
    .hero     { padding: 1.8rem 2.2rem 1.6rem; }
    .page-hero { padding: 1.1rem 1.6rem; }

    .hero h1, .page-hero h2 {
        color: white !important;
        margin: 0;
        font-weight: 700;
        letter-spacing: -0.01em;
    }
    .hero h1  { font-size: 2rem; }
    .page-hero h2 { font-size: 1.5rem; }

    .hero p, .page-hero p {
        color: rgba(255,255,255,0.82);
        margin: 0.4rem 0 0;
        font-size: 0.95rem;
        letter-spacing: 0.01em;
    }
    .hero .division {
        color: rgba(255,255,255,0.65);
        font-size: 0.82rem;
        margin: 0.2rem 0 0;
        letter-spacing: 0.01em;
    }

    /* ── Info cards ── */
    .info-card {
        background: #F2F8FD;
        border: 1px solid #C5DDF0;
        border-left: 4px solid #004C97;
        padding: 0.95rem 1.15rem;
        border-radius: 6px;
        margin-bottom: 1rem;
        font-size: 0.92rem;
        box-shadow: 0 1px 4px rgba(0,80,130,0.07);
    }
    .info-card strong { color: #004B78; }

    /* ── Narrative box ── */
    .narrative-box {
        background: #F2F8FD;
        border: 1px solid #C5DDF0;
        border-left: 4px solid #004C97;
        border-radius: 6px;
        padding: 0.85rem 1.1rem;
        font-size: 0.94rem;
        line-height: 1.65;
        margin-bottom: 0.6rem;
        box-shadow: 0 1px 3px rgba(0,80,130,0.06);
    }

    /* ── Primary button ── */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: #004C97;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.6rem 1.6rem;
        font-size: 0.97rem;
        font-weight: 600;
        letter-spacing: 0.01em;
        width: 100%;
        transition: background 0.18s, box-shadow 0.18s;
        box-shadow: 0 1px 4px rgba(0,60,150,0.2);
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: #003A7A;
        box-shadow: 0 2px 8px rgba(0,60,150,0.28);
    }

    /* ── Tabs ── */
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #004C97 !important;
        border-bottom-color: #004C97 !important;
    }

    /* ── Section headings ── */
    h3, h5 { color: #003A5C !important; }
</style>
""", unsafe_allow_html=True)

# ── Password gate ─────────────────────────────────────────────────────────────

def _check_password() -> bool:
    if st.session_state.get("_auth_ok"):
        return True

    st.markdown("""
    <div style="max-width:380px;margin:4rem auto 0;">
      <div style="
          background:linear-gradient(100deg,#002F5F 0%,#004C97 60%,#0062B8 100%);
          border-radius:10px;border-bottom:3px solid rgba(255,255,255,0.35);
          box-shadow:0 2px 12px rgba(0,40,100,0.22);
          padding:1.6rem 2rem 1.4rem;margin-bottom:1.6rem;text-align:center;">
        <div style="color:white;font-size:1.3rem;font-weight:700;letter-spacing:-0.01em;">WTO TPR IP Viz</div>
        <div style="color:rgba(255,255,255,0.75);font-size:0.82rem;margin-top:0.3rem;">
          Intellectual Property, Government Procurement and Competition Division
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        pwd = st.text_input("Password", type="password", key="_pwd_input",
                            placeholder="Enter access password")
        if pwd:
            if pwd == st.secrets.get("APP_PASSWORD", ""):
                st.session_state["_auth_ok"] = True
                st.rerun()
            else:
                st.error("Incorrect password. Please try again.")
    return False


if not _check_password():
    st.stop()

# ── Page navigation ────────────────────────────────────────────────────────────

pages = st.navigation([
    st.Page("pages/select_economy.py", title="Select Economy"),
    st.Page("pages/1_Country_Profile.py", title="IP Profile"),
    st.Page("pages/2_Excel_Generator.py", title="Excel Generator"),
    st.Page("pages/3_Methodology.py", title="Methodology"),
])
pages.run()
