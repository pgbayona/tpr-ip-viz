"""Select Economy — WTO member selector and app home."""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.transform.cleaning import WTO_MEMBERS

_CACHE_META  = _ROOT / "data" / "last_refreshed.json"
_LOCK_FILE   = _ROOT / "data" / ".prefetch_running"
_REFRESH_DAYS = 90


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _read_meta() -> dict | None:
    if not _CACHE_META.exists():
        return None
    try:
        return json.loads(_CACHE_META.read_text())
    except Exception:
        return None


def _cache_age_days(meta: dict) -> int:
    try:
        ts = datetime.fromisoformat(meta["refreshed_at"])
        return (datetime.now(timezone.utc) - ts).days
    except Exception:
        return 9999


def _trigger_refresh() -> None:
    subprocess.Popen(
        [sys.executable, str(_ROOT / "scripts" / "prefetch_data.py"), "--force"],
        stdout=open(_ROOT / "data" / "prefetch.log", "w"),
        stderr=subprocess.STDOUT,
    )


# ── Auto-refresh check ────────────────────────────────────────────────────────

meta = _read_meta()
is_running = _LOCK_FILE.exists()

if not is_running:
    if meta is None:
        _trigger_refresh()
        is_running = True
    elif _cache_age_days(meta) >= _REFRESH_DAYS:
        _trigger_refresh()
        is_running = True


# ── Hero header (with inline logo) ───────────────────────────────────────────

def _logo_html_snippet() -> str:
    svg_path = _ROOT / "app" / "static" / "wto_logo.svg"
    if svg_path.exists():
        svg = svg_path.read_text(encoding="utf-8")
        # Strip XML declaration and embed inline, constrained to 64px height
        svg = svg.replace('<?xml version="1.0" encoding="UTF-8" standalone="no"?>', "")
        svg = svg.replace("<svg ", '<svg style="height:90px;width:auto;display:block;" ', 1)
        return f'<div style="background:rgba(255,255,255,0.12);border-radius:8px;padding:0.55rem 0.8rem;">{svg}</div>'
    for p in (
        _ROOT / "app" / "static" / "wto_logo.png",
        _ROOT / "app" / "static" / "wto_logo.jpg",
    ):
        if p.exists():
            mime = f"image/{p.suffix[1:]}"
            b64 = base64.b64encode(p.read_bytes()).decode()
            return f'<img src="data:{mime};base64,{b64}" height="64" style="display:block;">'
    return ""

_logo_html = _logo_html_snippet()

st.markdown(f"""
<div class="hero" style="display:flex;justify-content:space-between;align-items:center;gap:1.5rem;">
  <div>
    <h1>WTO TPR&nbsp;IP&nbsp;Viz</h1>
    <p>Trade Policy Review &mdash; Intellectual Property Statistics Dashboard &amp; Excel Generator</p>
    <p class="division">Intellectual Property, Government Procurement and Competition Division</p>
  </div>
  {_logo_html}
</div>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([3, 2], gap="large")

# ── Economy selector ──────────────────────────────────────────────────────────
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

# ── Data cache status ─────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Data Cache")

cache_col, btn_col = st.columns([4, 1])

with cache_col:
    if is_running:
        st.info(
            "Data refresh in progress — fetching all WTO members from WIPO & WTO APIs. "
            "This runs in the background and may take several minutes. "
            "Check `data/prefetch.log` for progress."
        )
    elif meta is None:
        st.warning("No data cache found. A refresh has been started automatically.")
    else:
        age = _cache_age_days(meta)
        date_str = datetime.fromisoformat(meta["refreshed_at"]).strftime("%d %b %Y")
        ok = meta.get("success_count", "?")
        total = meta.get("total_countries", "?")
        failed = meta.get("failed_countries", [])
        msg = (
            f"Last refreshed: **{date_str}** ({age} days ago) · "
            f"{ok}/{total} countries · years {meta.get('start_year')}–{meta.get('end_year')}"
        )
        if failed:
            msg += f" · {len(failed)} failed: {', '.join(failed[:5])}{'…' if len(failed) > 5 else ''}"
        st.success(msg)

with btn_col:
    if not is_running:
        if st.button("Refresh Data", help="Re-fetch all country data from WIPO & WTO APIs"):
            _trigger_refresh()
            st.info("Refresh started in background. Check `data/prefetch.log` for progress.")
            st.rerun()
    else:
        st.button("Refreshing…", disabled=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "WTO Intellectual Property, Government Procurement and Competition Division · "
    "TPR IP Viz v1.0 · Data: WIPO IP Statistics Data Center & WTO Stats Portal"
)
