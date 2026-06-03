"""Country Profile — 5-tab interactive dashboard."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

from src.viz.profile import assemble_country_profile, CountryProfile
from src.viz import charts

st.set_page_config(
    page_title="Country Profile | TPR IP Viz",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
    .tab-header { font-size: 1.05rem; font-weight: 600; color: #005A8C; }
    .narrative-box {
        background: #F8FAFC;
        border: 1px solid #D0E4F0;
        border-radius: 6px;
        padding: 0.8rem 1rem;
        font-size: 0.95rem;
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)

# ── Guard ─────────────────────────────────────────────────────────────────────
if "country_name" not in st.session_state:
    st.warning(
        "No country selected. Please go to the **Home** page and click "
        "*Generate TPR IP Profile* first."
    )
    st.stop()

country_name = st.session_state["country_name"]
country_code = st.session_state.get("country_code", "")
START, END = 2010, 2024


@st.cache_data(ttl=3600, show_spinner=False)
def _load(name: str, s: int, e: int) -> CountryProfile:
    return assemble_country_profile(name, s, e)


# ── Page header ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(90deg,#005A8C,#00A9E0);
            padding:1rem 1.5rem;border-radius:8px;margin-bottom:1rem;">
  <h2 style="color:white;margin:0;">📊 {country_name} — IP Country Profile</h2>
  <p style="color:rgba(255,255,255,0.85);margin:0;">
    WIPO IP Statistics + WTO Services Trade · {START}–{END}
  </p>
</div>
""", unsafe_allow_html=True)

with st.spinner(f"Loading IP data for {country_name}…"):
    profile = _load(country_name, START, END)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 IP Overview",
    "📈 Time Series",
    "🏠 Resident vs Foreign",
    "💱 IP Services Trade",
    "📝 TPR Narrative",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — IP Overview
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.subheader(f"Latest IP Statistics — {country_name}")
    ov = profile.derived.get("overview", {})

    def _metric(label: str, key: str, unit: str = "") -> None:
        d = ov.get(key, {})
        val = d.get("latest_value")
        yr  = d.get("latest_year")
        dlt = d.get("yoy_delta_pct")
        yr_label = f" ({yr})" if yr else ""
        val_str  = f"{unit}{val:,.0f}" if val else "N/A"
        dlt_str  = f"{dlt:+.1f}% YoY" if dlt is not None else None
        st.metric(label=f"{label}{yr_label}", value=val_str, delta=dlt_str)

    # Patents
    st.markdown("##### Patents")
    c1, c2, c3 = st.columns(3)
    with c1: _metric("Applications", "Patent Applications")
    with c2: _metric("Grants",       "Patent Grants")
    with c3:
        pa = profile.patent_applications
        pg = profile.patent_grants
        if not pa.empty and not pg.empty and "total" in pa.columns and "total" in pg.columns:
            pa_v = pa[pa["total"].notna()].sort_values("year")
            pg_v = pg[pg["total"].notna()].sort_values("year")
            if not pa_v.empty and not pg_v.empty:
                merged = pa_v[["year","total"]].merge(pg_v[["year","total"]], on="year", suffixes=("_a","_g"))
                if not merged.empty and merged["total_a"].iloc[-1] > 0:
                    rate = merged["total_g"].iloc[-1] / merged["total_a"].iloc[-1] * 100
                    st.metric("Grant Rate", f"{rate:.1f}%")
                else:
                    st.metric("Grant Rate", "N/A")

    st.divider()

    # Trademarks
    st.markdown("##### Trademarks")
    c1, c2, _ = st.columns(3)
    with c1: _metric("TM Applications",  "Trademark Applications")
    with c2: _metric("TM Registrations", "Trademark Registrations")

    st.divider()

    # Designs
    st.markdown("##### Industrial Designs")
    c1, c2, _ = st.columns(3)
    with c1: _metric("Design Applications",  "Industrial Design Applications")
    with c2: _metric("Design Registrations", "Industrial Design Registrations")

    st.divider()

    # Utility Models + GIs
    st.markdown("##### Utility Models & Geographical Indications")
    c1, c2, c3, _ = st.columns(4)
    with c1: _metric("UM Applications", "Utility Model Applications")
    with c2: _metric("UM Grants",       "Utility Model Grants")
    with c3: _metric("GIs",             "Geographical Indications")

    st.divider()

    # IP Services
    st.markdown("##### Trade in IP Services (USD million)")
    c1, c2, _ = st.columns(3)
    with c1:
        d = ov.get("IP Service Exports", {})
        val = d.get("latest_value")
        yr  = d.get("latest_year")
        dlt = d.get("yoy_delta_pct")
        st.metric(
            f"IP Exports ({yr or '—'})",
            f"USD {val:.1f}M" if val else "N/A",
            f"{dlt:+.1f}% YoY" if dlt else None,
        )
    with c2:
        d = ov.get("IP Service Imports", {})
        val = d.get("latest_value")
        yr  = d.get("latest_year")
        dlt = d.get("yoy_delta_pct")
        st.metric(
            f"IP Imports ({yr or '—'})",
            f"USD {val:.1f}M" if val else "N/A",
            f"{dlt:+.1f}% YoY" if dlt else None,
        )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Time Series
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader(f"IP Indicator Trends — {country_name} ({START}–{END})")

    INDICATOR_MAP = {
        "Patent Applications":              profile.patent_applications,
        "Patent Grants":                    profile.patent_grants,
        "Trademark Applications":           profile.trademark_applications,
        "Trademark Registrations":          profile.trademark_registrations,
        "Industrial Design Applications":   profile.design_applications,
        "Industrial Design Registrations":  profile.design_registrations,
        "Utility Model Applications":       profile.utility_model_applications,
        "Utility Model Grants":             profile.utility_model_grants,
        "Geographical Indications":         profile.geographical_indications,
    }

    selected = st.selectbox("Select indicator", list(INDICATOR_MAP.keys()), key="ts_sel")
    df_sel = INDICATOR_MAP[selected]

    if selected == "Geographical Indications":
        fig = charts.gi_bar_chart(df_sel, country_name)
    else:
        fig = charts.time_series_chart(df_sel, selected, country_name)

    st.plotly_chart(fig, use_container_width=True)

    if not df_sel.empty:
        with st.expander("View data table"):
            st.dataframe(df_sel, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Resident vs Foreign
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.subheader(f"Resident vs Non-Resident Filing Activity — {country_name}")

    ORIGIN_MAP = {
        "Patent Applications":              profile.patent_applications,
        "Patent Grants":                    profile.patent_grants,
        "Trademark Applications":           profile.trademark_applications,
        "Trademark Registrations":          profile.trademark_registrations,
        "Industrial Design Applications":   profile.design_applications,
        "Industrial Design Registrations":  profile.design_registrations,
        "Utility Model Applications":       profile.utility_model_applications,
        "Utility Model Grants":             profile.utility_model_grants,
    }

    selected_o = st.selectbox("Select indicator", list(ORIGIN_MAP.keys()), key="orig_sel")
    df_o = ORIGIN_MAP[selected_o]

    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(
            charts.resident_foreign_bar(df_o, selected_o, country_name),
            use_container_width=True,
        )
    with col_b:
        st.plotly_chart(
            charts.resident_share_line(df_o, selected_o, country_name),
            use_container_width=True,
        )

    if not df_o.empty and "resident_share_pct" in df_o.columns:
        valid_rs = df_o[df_o["resident_share_pct"].notna()].sort_values("year")
        if not valid_rs.empty:
            row = valid_rs.iloc[-1]
            yr = int(row["year"])
            share = float(row["resident_share_pct"])
            msg = (
                f"In **{yr}**, resident applicants accounted for **{share:.1f}%** "
                f"of {selected_o.lower()} in {country_name}."
            )
            st.info(msg)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — Trade in IP Services
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.subheader(f"Trade in Intellectual Property Services — {country_name}")

    ip_svc = profile.ip_services

    if ip_svc.empty:
        st.warning(
            "IP services data is not available for this country.  "
            "Check that `WTO_API_KEY` is set in your `.env` file."
        )
    else:
        st.plotly_chart(
            charts.ip_services_chart(ip_svc, country_name),
            use_container_width=True,
        )

        st.markdown("##### Summary")
        c1, c2, c3 = st.columns(3)

        exp_rows = ip_svc[ip_svc["exports_usd"].notna()].sort_values("year")
        imp_rows = ip_svc[ip_svc["imports_usd"].notna()].sort_values("year")

        with c1:
            if not exp_rows.empty:
                last_exp = exp_rows.iloc[-1]
                st.metric(
                    f"IP Exports ({int(last_exp['year'])})",
                    f"USD {last_exp['exports_usd']:.1f}M",
                )
        with c2:
            if not imp_rows.empty:
                last_imp = imp_rows.iloc[-1]
                st.metric(
                    f"IP Imports ({int(last_imp['year'])})",
                    f"USD {last_imp['imports_usd']:.1f}M",
                )
        with c3:
            if not exp_rows.empty and not imp_rows.empty:
                balance = last_exp["exports_usd"] - last_imp["imports_usd"]
                st.metric(
                    "Trade Balance",
                    f"USD {balance:.1f}M",
                    delta="Surplus" if balance >= 0 else "Deficit",
                    delta_color="normal" if balance >= 0 else "inverse",
                )

        with st.expander("View data table"):
            st.dataframe(ip_svc, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — TPR Narrative
# ─────────────────────────────────────────────────────────────────────────────
with tab5:
    st.subheader(f"Auto-Generated TPR Narrative Snippets — {country_name}")
    st.caption(
        "These snippets are ready to paste into TPR report drafts. "
        "Review and edit as appropriate before submission."
    )

    narratives = profile.derived.get("narratives", [])
    valid_narratives = [
        n for n in narratives if "not available" not in n.get("text", "")
    ]

    if not valid_narratives:
        st.info("No narrative data available. Check that the country data loaded successfully.")
    else:
        for item in valid_narratives:
            ind  = item.get("indicator", "")
            text = item.get("text", "")
            with st.expander(f"**{ind}**", expanded=False):
                st.markdown(f'<div class="narrative-box">{text}</div>', unsafe_allow_html=True)
                st.code(text, language=None)

    st.divider()
    if valid_narratives:
        combined = "\n\n".join(
            f"{n['indicator']}:\n{n['text']}" for n in valid_narratives
        )
        c1, _ = st.columns([1, 3])
        with c1:
            st.download_button(
                label="⬇️ Download all as .txt",
                data=combined,
                file_name=f"TPR_IP_Narrative_{country_code}.txt",
                mime="text/plain",
            )
        st.text_area(
            "All narrative snippets",
            value=combined,
            height=320,
            label_visibility="collapsed",
        )
