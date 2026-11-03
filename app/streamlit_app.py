"""Airline Delay Intelligence - Streamlit dashboard (entry point).

Run from the project root:
    streamlit run app/streamlit_app.py

Prerequisite: the pipeline has produced data/processed/flights_clean.parquet
    python scripts/run_pipeline.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow `import data`, `import theme` ...

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Airline Delay Intelligence", page_icon="✈️", layout="wide", initial_sidebar_state="expanded")

import theme as T  # noqa: E402
import views as V  # noqa: E402

import data as D  # noqa: E402

st.markdown(T.CSS, unsafe_allow_html=True)

PAGES = {
    "🛫  Control Tower": V.page_overview,
    "🏢  Airlines": V.page_airlines,
    "🗺️  Airports & Routes": V.page_airports,
    "🕒  Time Patterns": V.page_time,
    "🔬  Delay Anatomy": V.page_anatomy,
    "🌪️  Cancellations & Events": V.page_cancellations,
    "🧭  Route Finder": V.page_route,
    "ℹ️  About & Method": V.page_about,
}

# ------------------------------------------------------------------ data guard
full = D.load_data()
if full is None:
    st.markdown(T.hero("Airline Delay Intelligence", "Flight data not found", ["setup needed"]), unsafe_allow_html=True)
    st.error(f"Processed data not found at `{D.data_path()}`.")
    st.markdown("Place the raw CSV in `data/raw/flight_random_1million.csv` and run:\n```bash\npython scripts/run_pipeline.py\n```")
    st.stop()

# ------------------------------------------------------------------ filter options / defaults
AIRLINES = full["airline_name"].value_counts().index.astype(str).tolist()
ORIGINS = full["origin_label"].value_counts().index.astype(str).tolist()
MONTHS = D.MONTH_NAMES
FILTER_KEYS = ["f_airlines", "f_months", "f_days", "f_dayparts", "f_hauls", "f_origins", "f_extreme", "f_winsor"]


def reset_filters() -> None:
    """Callback: delete the filter widgets' state so every widget falls back to its own default value."""
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown('<div class="sb-brand">✈ Control Tower</div><div class="sb-sub">Airline Delay Intelligence · 2024</div>', unsafe_allow_html=True)
    page = st.radio("Navigate", list(PAGES), label_visibility="collapsed", key="page")
    st.markdown("---")
    st.markdown("### Flight filters")
    st.multiselect("Airline", AIRLINES, key="f_airlines", placeholder="All airlines")
    st.select_slider("Months", options=MONTHS, value=(MONTHS[0], MONTHS[-1]), key="f_months")
    st.multiselect("Day of week", D.DAY_NAMES, key="f_days", placeholder="All days")
    st.multiselect("Part of day", D.RULES["daypart_labels"], key="f_dayparts", placeholder="All day")
    st.multiselect("Haul length", D.RULES["haul_labels"], key="f_hauls", placeholder="All distances")
    st.multiselect("Origin airport", ORIGINS, key="f_origins", placeholder="All airports")
    st.markdown("### Outlier handling")
    st.toggle("Exclude extreme delays (≥ 6 h)", value=False, key="f_extreme")
    st.toggle("Winsorized averages (robust)", value=True, key="f_winsor")
    st.button("↺ Reset filters", on_click=reset_filters, width="stretch")

ss = st.session_state
m_lo, m_hi = ss["f_months"]
FILTERS = D.Filters(
    airlines=tuple(ss["f_airlines"]), months=(MONTHS.index(m_lo) + 1, MONTHS.index(m_hi) + 1),
    days=tuple(ss["f_days"]), dayparts=tuple(ss["f_dayparts"]), hauls=tuple(ss["f_hauls"]),
    origins=tuple(ss["f_origins"]), drop_extreme=bool(ss["f_extreme"]), winsor=bool(ss["f_winsor"]),
)
n_sel = len(D.get_filtered(FILTERS))
with st.sidebar:
    st.markdown(f'<div class="sb-count">✈ {n_sel:,} flights selected<br>{100 * n_sel / len(full):.1f}% of {len(full):,}</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ hero + page
active = [n for n, on in (("airlines", FILTERS.airlines), ("origins", FILTERS.origins), ("days", FILTERS.days),
                          ("dayparts", FILTERS.dayparts), ("hauls", FILTERS.hauls)) if on]
tags = [f"{n_sel:,} flights", f"{m_lo}–{m_hi}", "winsorized" if FILTERS.winsor else "raw averages"]
if FILTERS.drop_extreme:
    tags.append("extreme delays excluded")
if active:
    tags.append("filtered: " + ", ".join(active))
st.markdown(T.hero("Airline Delay Intelligence", "US domestic flights · reliability, delays and cancellations · where, when and why", tags),
            unsafe_allow_html=True)

# Plotly sizes charts from the container width at first paint; Streamlit's layout can still be settling then, which leaves
# charts on a freshly opened page cropped until the window is resized. A tiny script fires resize events shortly after load.
_resize_js = (f"<script>/* {page} */const f=()=>window.parent.dispatchEvent(new Event('resize'));"
              "[100,400,900,1800,3000].forEach(t=>setTimeout(f,t));</script>")
if hasattr(st, "iframe"):  # Streamlit >= 1.5x: st.components.v1.html is deprecated in favour of st.iframe
    st.iframe(_resize_js, height=1)
else:
    import streamlit.components.v1 as components
    components.html(_resize_js, height=0)

PAGES[page](FILTERS)
st.caption("Source: US BTS on-time performance, 2024 (1M-row random sample of ~7M flights). Delay = arrival ≥ 15 min late. "
           "Descriptive analysis: associations, not causes.")
