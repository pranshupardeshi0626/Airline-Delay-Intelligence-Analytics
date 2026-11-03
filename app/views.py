"""Dashboard pages. Each ``page_*`` function renders one page for a given ``Filters`` selection.

All numbers come from ``data.py`` (which wraps ``airline_delay.analysis.metrics``), so every figure here
is identical to what the batch pipeline writes to ``reports/tables``.
"""
from __future__ import annotations

import html
import itertools
import json
from contextlib import contextmanager

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import theme as T
from airports_geo import AIRPORT_COORDS

import data as D

_keys = itertools.count()
SCALE = [[0, T.SKY_LIGHT], [0.5, T.AMBER], [1, T.ALERT]]


# --------------------------------------------------------------------------- helpers
def begin() -> None:
    """Reset the per-page widget-key counter (keeps Plotly element ids stable across reruns)."""
    global _keys
    _keys = itertools.count()


def show(fig: go.Figure) -> None:
    """Render a Plotly figure full width."""
    st.plotly_chart(fig, width="stretch", key=f"plt{next(_keys)}")


def md(s: str) -> None:
    """Render trusted HTML."""
    st.markdown(s, unsafe_allow_html=True)


def cards(items: list[str]) -> None:
    """Row of KPI cards."""
    for col, c in zip(st.columns(len(items)), items, strict=False):
        col.markdown(c, unsafe_allow_html=True)


def esc(x) -> str:
    """HTML-escape a dynamic value."""
    return html.escape(str(x))


@contextmanager
def safe(what: str = "section"):
    """Show a friendly message (instead of a stack trace) when a very narrow filter leaves too little data to draw ``what``.

    Only data-shape errors are swallowed; Streamlit's own control-flow exceptions pass through.
    """
    try:
        yield
    except (ValueError, IndexError, KeyError):
        st.info(f"Not enough data to draw this {what} with the current filters. Widen the selection to see it.")


def need_data(f: D.Filters) -> bool:
    """Warn and return False when the filters leave no flights."""
    if len(D.get_filtered(f)) == 0:
        st.warning("No flights match the current filters. Widen the selection in the sidebar.")
        return False
    return True


def prop_ci(p_pct: pd.Series, n: pd.Series) -> pd.Series:
    """95 % normal-approximation margin (percentage points) for a proportion given in %."""
    p = (p_pct / 100).clip(0, 1)
    return 1.96 * np.sqrt(p * (1 - p) / n.replace(0, np.nan)) * 100


def mo(m) -> str:
    """Month number -> short name."""
    return D.MONTH_NAMES[int(m) - 1]


# --------------------------------------------------------------------------- 1. overview
def page_overview(f: D.Filters) -> None:
    begin()
    if not need_data(f):
        return
    k, b = D.kpis(f), D.baseline_kpis()
    df = D.get_filtered(f)
    arr_key = "avg_arr_delay_winsorized_min" if f.winsor else "avg_arr_delay_min"
    ext_pct = 100 * k["extreme"] / max(k["completed_flights"], 1)

    cards([
        T.kpi_card("Flights", f"{k['total_flights']:,}", f"{100 * k['total_flights'] / b['total_flights']:.0f}% of the network", T.SKY),
        T.kpi_card("On-time", f"{k['ontime_pct']:.1f}%", f"arrivals < {D.RULES['delay_threshold_minutes']} min late", T.GOOD,
                   k["ontime_pct"] - b["ontime_pct"], good_when_lower=False, delta_unit=" pp"),
        T.kpi_card("Cancelled", f"{k['cancel_rate_pct']:.2f}%", f"diverted {k['diverted_rate_pct']:.2f}%", T.PURPLE,
                   k["cancel_rate_pct"] - b["cancel_rate_pct"], delta_fmt="{:+.2f}", delta_unit=" pp"),
        T.kpi_card("Avg delay", f"{k[arr_key]:.1f} min", f"arrival · median {k['median_arr_delay_min']:.0f} min", T.AMBER,
                   k[arr_key] - b[arr_key], delta_unit=" min"),
        T.kpi_card("P90 delay", f"{k['p90_arr_delay_min']:.0f} min", "the 'bad day' experience", T.ALERT,
                   k["p90_arr_delay_min"] - b["p90_arr_delay_min"], delta_unit=" min"),
        T.kpi_card("Extreme", f"{k['extreme']:,}", f"flights ≥ 6 h late ({ext_pct:.2f}%)", T.NAVY),
    ])

    md(T.section("Network pulse"))
    c1, c2, c3 = st.columns([1.05, 1.05, 1.9])
    with c1:
        g = go.Figure(go.Indicator(
            mode="gauge+number+delta" if abs(k["ontime_pct"] - b["ontime_pct"]) >= 0.005 else "gauge+number",
            value=k["ontime_pct"], number={"suffix": "%", "font": {"size": 38}},
            delta={"reference": b["ontime_pct"], "suffix": " pp", "increasing": {"color": T.GOOD}, "decreasing": {"color": T.ALERT}},
            title={"text": "On-time performance"},
            gauge={"axis": {"range": [50, 100]}, "bar": {"color": T.SKY},
                   "steps": [{"range": [50, 70], "color": "#FADBD2"}, {"range": [70, 80], "color": "#FFF0C9"},
                             {"range": [80, 100], "color": "#D6F2E7"}],
                   "threshold": {"line": {"color": T.NAVY, "width": 3}, "value": b["ontime_pct"]}}))
        show(T.style(g, height=330))
    with c2:
        c = df["arrival_status"].value_counts().rename_axis("status").reset_index(name="flights")
        colors = {"Arrived Early": T.GOOD, "Arrived On Time": T.TEAL, "Arrived Late": T.ALERT, "Cancelled": T.PURPLE,
                  "Diverted": T.AMBER}
        fig = px.pie(c, names="status", values="flights", hole=0.58, color="status", color_discrete_map=colors)
        fig.update_traces(textinfo="percent", sort=False)
        fig.update_layout(legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"), showlegend=True)
        show(T.style(fig, "Arrival status mix", 330))
    with c3:
        m = D.group(f, ("month",))
        fig = go.Figure()
        fig.add_bar(x=[mo(i) for i in m["month"]], y=m["delay_rate_pct"], name="Delay rate (%)", marker_color=T.SKY)
        fig.add_scatter(x=[mo(i) for i in m["month"]], y=m["cancel_rate_pct"], name="Cancel rate (%)", yaxis="y2",
                        mode="lines+markers", line=dict(color=T.ALERT, width=3))
        fig.update_layout(yaxis=dict(title="Delay rate (%)"),
                          yaxis2=dict(title="Cancel rate (%)", overlaying="y", side="right", showgrid=False))
        show(T.style(fig, "Seasonality: delays vs cancellations", 330))

    with safe("section"):
        md(T.section("Why delays happen, and how bad the tail is"))
        c1, c2 = st.columns(2)
        cz, sev = D.causes(f), D.severity(f)
        with c1:
            fig = px.bar(cz.sort_values("share_pct"), x="share_pct", y="cause", orientation="h", text="share_pct", color="cause",
                         color_discrete_map=T.CAUSE_COLORS, labels={"share_pct": "% of delay minutes", "cause": ""})
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(showlegend=False)
            show(T.style(fig, "Share of delay minutes by cause (flights ≥ 15 min late)", 360))
        with c2:
            s = sev.melt(id_vars="severity", value_vars=["pct_of_delayed_flights", "pct_of_delay_minutes"], var_name="m", value_name="pct")
            s["m"] = s["m"].map({"pct_of_delayed_flights": "% of delayed flights", "pct_of_delay_minutes": "% of delay minutes"})
            fig = px.bar(s, x="severity", y="pct", color="m", barmode="group", text="pct",
                         color_discrete_sequence=[T.SKY_LIGHT, T.ALERT], labels={"severity": "", "pct": "%"})
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            show(T.style(fig, "A few extreme delays carry a large share of the minutes", 360))

        top = cz.sort_values("share_pct", ascending=False).iloc[0]
        ext = sev.iloc[-1]
        worst_m = D.group(f, ("month",)).sort_values("delay_rate_pct", ascending=False).iloc[0]
        md(T.note(f"<b class='k'>Pilot's notes</b> · <b>{esc(top['cause'])}</b> drives {top['share_pct']:.1f}% of delay minutes. "
                  f"Flights delayed <b>{esc(ext['severity'])}</b> are only {ext['pct_of_delayed_flights']:.1f}% of delayed flights "
                  f"but {ext['pct_of_delay_minutes']:.1f}% of delay minutes. "
                  f"The worst month in this selection is <b>{mo(worst_m['month'])}</b> ({worst_m['delay_rate_pct']:.1f}% delayed).", "sky"))


# --------------------------------------------------------------------------- 2. airlines
AIRLINE_METRICS = {
    "Delay rate (%)": ("delay_rate_pct", "completed", "delay_rate_pct"),
    "Cancellation rate (%)": ("cancel_rate_pct", "flights", "cancel_rate_pct"),
    "Extreme-delay rate (%)": ("extreme_rate_pct", None, None),
    "Avg departure delay (min)": ("DEP", None, None),
    "Avg arrival delay (min)": ("ARR", None, None),
    "Median arrival delay (min)": ("median_arr_delay", None, None),
    "90th-percentile arrival delay (min)": ("p90_arr_delay", None, None),
}


def page_airlines(f: D.Filters) -> None:
    begin()
    if not need_data(f):
        return
    dep_c, arr_c = D.dcols(f)
    c1, c2 = st.columns([2, 1])
    metric = c1.selectbox("Rank airlines by", list(AIRLINE_METRICS), index=0)
    min_fl = c2.slider("Minimum flights per airline", 50, 3000, 300, step=50)
    col, n_col, _ = AIRLINE_METRICS[metric]
    col = {"DEP": dep_c, "ARR": arr_c}.get(col, col)
    a = D.group(f, ("airline_name",), min_fl)
    if a.empty:
        st.warning("No airline has enough flights with these filters. Lower the minimum.")
        return
    a = a.sort_values(col)
    k = D.kpis(f)
    ref = {"delay_rate_pct": k["delay_rate_pct"], "cancel_rate_pct": k["cancel_rate_pct"]}.get(col)

    cards([
        T.kpi_card("Airlines shown", f"{len(a)}", f"≥ {min_fl} flights each", T.SKY),
        T.kpi_card("Best", str(a.iloc[0]["airline_name"]), f"{metric.split(' (')[0]}: {a.iloc[0][col]:.1f}", T.GOOD),
        T.kpi_card("Worst", str(a.iloc[-1]["airline_name"]), f"{metric.split(' (')[0]}: {a.iloc[-1][col]:.1f}", T.ALERT),
        T.kpi_card("Spread (worst - best)", f"{a.iloc[-1][col] - a.iloc[0][col]:.1f}", metric.split(" (")[0], T.AMBER),
    ])

    fig = px.bar(a, x=col, y="airline_name", orientation="h", color=col, color_continuous_scale=SCALE, text=col,
                 labels={col: metric, "airline_name": ""})
    if n_col:  # 95% confidence whiskers for proportions
        fig.update_traces(error_x=dict(type="data", array=prop_ci(a[col], a[n_col]), color=T.NAVY, thickness=1.2))
    fig.update_traces(texttemplate="%{text:.1f}", textposition="inside", insidetextanchor="end",
                      textfont=dict(color=T.NAVY, size=12))  # label inside the bar: no clash with CI whiskers
    if ref is not None:
        fig.add_vline(x=ref, line_dash="dash", line_color=T.NAVY, annotation_text="selection avg", annotation_position="top")
    fig.update_layout(coloraxis_showscale=False)
    show(T.style(fig, f"Airlines ranked by {metric.lower()}", max(380, 34 * len(a) + 110)))
    if n_col:
        md(T.note("Whiskers are 95% confidence intervals: airlines whose whiskers overlap are <b>not statistically different</b>.", "sky"))

    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(a, x="delay_rate_pct", y="cancel_rate_pct", size="flights", color="avg_arr_delay_w" if f.winsor else "avg_arr_delay",
                         text="airline_name", color_continuous_scale=SCALE, size_max=48,
                         labels={"delay_rate_pct": "Delay rate (%)", "cancel_rate_pct": "Cancellation rate (%)", "color": "Avg arr delay"})
        fig.update_traces(textposition="top center")
        fig.add_vline(x=a["delay_rate_pct"].median(), line_dash="dot", line_color="grey")
        fig.add_hline(y=a["cancel_rate_pct"].median(), line_dash="dot", line_color="grey")
        fig.update_layout(coloraxis_colorbar=dict(title="Avg arr<br>delay"))
        show(T.style(fig, "Reliability scorecard (bubble = flights)", 480))
    with c2:
        cz = D.causes(f, "airline_name")
        cz = cz[cz["airline_name"].isin(a["airline_name"])].sort_values("Late Aircraft")
        fig = px.bar(cz, y="airline_name", x=["Carrier", "Weather", "NAS", "Security", "Late Aircraft"], orientation="h",
                     color_discrete_map=T.CAUSE_COLORS, labels={"value": "% of delay minutes", "airline_name": "", "variable": "Cause"})
        show(T.style(fig, "What causes each airline's delay minutes?", 480))

    md(T.section("Airline scorecard table"))
    t = a.sort_values("delay_rate_pct", ascending=False)[["airline_name", "flights", "delay_rate_pct", "cancel_rate_pct", "diverted_rate_pct",
                                                           "median_arr_delay", arr_c, "p90_arr_delay", "extreme_delays"]]
    st.dataframe(t, hide_index=True, width="stretch", column_config={
        "airline_name": "Airline", "flights": st.column_config.NumberColumn("Flights", format="%d"),
        "delay_rate_pct": st.column_config.ProgressColumn("Delay rate %", min_value=0, max_value=40, format="%.1f"),
        "cancel_rate_pct": st.column_config.ProgressColumn("Cancel rate %", min_value=0, max_value=5, format="%.2f"),
        "diverted_rate_pct": "Diverted %", "median_arr_delay": "Median arr (min)", arr_c: "Avg arr (min)",
        "p90_arr_delay": "P90 arr (min)", "extreme_delays": "Extreme delays"})
    st.download_button("⬇ Download airline table (CSV)", t.to_csv(index=False), "airline_scorecard.csv", "text/csv")


# --------------------------------------------------------------------------- 3. airports & routes
AIRPORT_METRICS = {
    "Delay rate (%)": "delay_rate_pct", "Cancellation rate (%)": "cancel_rate_pct", "Avg departure delay (min)": "DEP",
    "Avg arrival delay (min)": "ARR", "Flights": "flights",
}


def page_airports(f: D.Filters) -> None:
    begin()
    if not need_data(f):
        return
    dep_c, arr_c = D.dcols(f)
    c1, c2, c3, c4 = st.columns([1.2, 1.6, 1.3, 1.1])
    side = c1.radio("Airport role", ["Origin", "Destination"], horizontal=True)
    metric = c2.selectbox("Colour / rank by", list(AIRPORT_METRICS), index=2)
    min_fl = c3.slider("Min flights", 100, 3000, D.RULES["min_flights_airport"], step=100)
    topn = c4.slider("Top N", 5, 30, 15)
    col = {"DEP": dep_c, "ARR": arr_c}.get(AIRPORT_METRICS[metric], AIRPORT_METRICS[metric])
    lab = "origin_label" if side == "Origin" else "dest_label"
    a = D.group(f, (lab,), min_fl)
    if a.empty:
        st.warning("No airports above the minimum flight count. Lower it.")
        return
    a = a.assign(code=a[lab].astype(str).str.split(" ").str[0])
    a["lat"] = a["code"].map(lambda c: AIRPORT_COORDS.get(c, (np.nan, np.nan))[0])
    a["lon"] = a["code"].map(lambda c: AIRPORT_COORDS.get(c, (np.nan, np.nan))[1])
    mapped = a.dropna(subset=["lat"])

    md(T.section(f"{side} airport map"))
    style = st.radio("Map style", ["Outline map (loads map data from the internet)", "Plain lat/lon (works offline)"], horizontal=True,
                     help="If the outline map is blank (no internet / blocked CDN), switch to the plain lat/lon view.")
    hover = {"flights": ":,", "delay_rate_pct": ":.1f", "cancel_rate_pct": ":.2f", "lat": False, "lon": False}
    if style.startswith("Outline"):
        fig = px.scatter_geo(mapped, lat="lat", lon="lon", size="flights", color=col, hover_name=lab, scope="usa",
                             color_continuous_scale=SCALE, size_max=34, hover_data=hover, labels={col: metric})
        fig.update_geos(showland=True, landcolor="#EAF1F8", showlakes=True, lakecolor="#D6E8F8", showcountries=False,
                        showsubunits=True, subunitcolor="#FFFFFF", bgcolor="rgba(0,0,0,0)")
    else:  # contiguous US only; equal-ish aspect (1 deg lat ~ 1.25 deg lon at 38N)
        lower48 = mapped[mapped["lon"].between(-125, -66) & mapped["lat"].between(24, 50)]
        fig = px.scatter(lower48, x="lon", y="lat", size="flights", color=col, hover_name=lab, color_continuous_scale=SCALE,
                         size_max=34, hover_data=hover, labels={col: metric, "lon": "Longitude", "lat": "Latitude"})
        fig.update_yaxes(scaleanchor="x", scaleratio=1.25)
    fig.update_layout(coloraxis_colorbar=dict(title=metric.split(" (")[0]))
    show(T.style(fig, f"Airports coloured by {metric.lower()} (bubble = flights)", 520))
    st.caption(f"Showing {len(mapped)} of {len(a)} airports above the minimum on the map (coordinates are approximate and "
               "available for the busiest airports; all airports appear in the rankings below).")

    c1, c2 = st.columns([1.2, 1])
    ranked = a.sort_values(col, ascending=False).head(topn).sort_values(col)
    with c1:
        fig = px.bar(ranked, x=col, y=lab, orientation="h", color=col, color_continuous_scale=SCALE, text=col,
                     labels={col: metric, lab: ""})
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False)
        fig.update_layout(coloraxis_showscale=False)
        show(T.style(fig, f"Top {topn} {side.lower()} airports by {metric.lower()}", max(420, 28 * topn + 110)))
    with c2:
        fig = px.scatter(a, x="flights", y=dep_c, color="cancel_rate_pct", hover_name=lab, color_continuous_scale=SCALE,
                         log_x=True, labels={"flights": "Flights (log scale)", dep_c: "Avg dep delay (min)", "cancel_rate_pct": "Cancel %"})
        show(T.style(fig, "Is bigger worse? Volume vs delay", max(420, 28 * topn + 110)))

    md(T.section("Route bottlenecks"))
    c1, c2 = st.columns(2)
    rmin = c1.slider("Min flights per route", 30, 500, D.RULES["min_flights_route"], step=10)
    rmetric = c2.selectbox("Rank routes by", ["Avg arrival delay (min)", "Delay rate (%)", "Cancellation rate (%)"])
    rcol = {"Avg arrival delay (min)": arr_c, "Delay rate (%)": "delay_rate_pct", "Cancellation rate (%)": "cancel_rate_pct"}[rmetric]
    r = D.group(f, ("route",), rmin)
    if r.empty:
        st.info("No routes above the minimum flight count.")
        return
    worst = r.sort_values(rcol, ascending=False).head(10)
    board = pd.DataFrame({"Route": worst["route"].astype(str), "Flights": worst["flights"].astype(int),
                          "Delay %": worst["delay_rate_pct"].round(1), "Cancel %": worst["cancel_rate_pct"].round(2),
                          "Avg arr (min)": worst[arr_c].round(1)})
    md(T.board_table(board, f"Most troubled routes · ranked by {rmetric}", hot_col="Delay %", hot_threshold=30))
    md(T.note("Route samples are small (often 100-300 flights): treat this board as a <b>lead list to investigate</b>, not a verdict.", "red"))
    st.download_button("⬇ Download route table (CSV)", r.sort_values(rcol, ascending=False).to_csv(index=False), "routes.csv", "text/csv")


# --------------------------------------------------------------------------- 4. time patterns
HEAT_METRICS = {"Avg departure delay (min)": ("DEP", 1.0), "Delay rate (%)": ("is_arr_delayed", 100.0),
                "Cancellation rate (%)": ("cancelled", 100.0)}


def page_time(f: D.Filters) -> None:
    begin()
    if not need_data(f):
        return
    dep_c, _ = D.dcols(f)
    h = D.group(f, ("scheduled_dep_hour",)).sort_values("scheduled_dep_hour")
    best, worst = h.sort_values(dep_c).iloc[0], h.sort_values(dep_c, ascending=False).iloc[0]
    cards([
        T.kpi_card("Calmest hour", f"{int(best['scheduled_dep_hour']):02d}:00", f"avg dep delay {best[dep_c]:.1f} min", T.GOOD),
        T.kpi_card("Roughest hour", f"{int(worst['scheduled_dep_hour']):02d}:00", f"avg dep delay {worst[dep_c]:.1f} min", T.ALERT),
        T.kpi_card("Delay-rate swing", f"{h['delay_rate_pct'].max() - h['delay_rate_pct'].min():.1f} pp", "worst vs best hour", T.AMBER),
    ])

    md(T.section("Delays build through the day"))
    fig = go.Figure()
    fig.add_bar(x=h["scheduled_dep_hour"], y=h["cancel_rate_pct"], name="Cancel rate (%)", yaxis="y2", marker_color="rgba(123,94,167,.35)")
    fig.add_scatter(x=h["scheduled_dep_hour"], y=h[dep_c], name="Avg departure delay (min)", mode="lines+markers",
                    line=dict(color=T.ALERT, width=4))
    fig.update_layout(xaxis=dict(title="Scheduled departure hour", dtick=1, range=[-0.6, 23.6]),
                      yaxis=dict(title="Avg departure delay (min)", rangemode="tozero"),
                      yaxis2=dict(title="Cancel rate (%)", overlaying="y", side="right", showgrid=False, rangemode="tozero"))
    show(T.style(fig, "Hourly delay & cancellation profile", 420))

    with safe("heatmap"):
        md(T.section("High-risk windows"))
        c1, c2 = st.columns([1, 1])
        rows = c1.radio("Rows", ["Month", "Day of week"], horizontal=True)
        hm = c2.selectbox("Metric", list(HEAT_METRICS))
        val, scale = HEAT_METRICS[hm]
        val = dep_c.replace("avg_dep_delay", "dep_delay") if val == "DEP" else val
        index = "month" if rows == "Month" else "day_name"
        p = D.pivot(f, index, "scheduled_dep_hour", val, scale)
        if index == "month":
            p.index = [mo(i) for i in p.index]
            p = p.reindex([m for m in D.MONTH_NAMES if m in p.index])
        else:
            p = p.reindex([d for d in D.DAY_NAMES if d in p.index])
        fig = px.imshow(p, aspect="auto", color_continuous_scale=SCALE, text_auto=".0f",
                        labels=dict(x="Scheduled departure hour", y="", color=hm))
        show(T.style(fig, f"{hm}: {rows.lower()} × hour", 520 if rows == "Month" else 400))

    with safe("section"):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = D.group(f, ("day_name",))
            d = d.set_index("day_name").reindex([x for x in D.DAY_NAMES if x in set(d["day_name"].astype(str))]).reset_index()
            fig = px.bar(d, x="day_name", y="delay_rate_pct", color="delay_rate_pct", color_continuous_scale=SCALE, text="delay_rate_pct",
                         labels={"day_name": "", "delay_rate_pct": "Delay rate (%)"})
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
            fig.update_layout(coloraxis_showscale=False)
            show(T.style(fig, "Delay rate by weekday", 380))
        with c2:
            dp = D.group(f, ("dep_daypart",))
            order = [x for x in D.RULES["daypart_labels"] if x in set(dp["dep_daypart"].astype(str))]
            dp = dp.set_index("dep_daypart").reindex(order).reset_index()
            fig = px.bar(dp, x="dep_daypart", y="delay_rate_pct", color="delay_rate_pct", color_continuous_scale=SCALE, text="delay_rate_pct",
                         labels={"dep_daypart": "", "delay_rate_pct": "Delay rate (%)"})
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
            fig.update_layout(coloraxis_showscale=False, xaxis_tickangle=-25)
            show(T.style(fig, "Delay rate by part of day", 380))
        with c3:
            s = D.group(f, ("season",))
            fig = px.bar(s, x="season", y=["delay_rate_pct", "cancel_rate_pct"], barmode="group",
                         color_discrete_sequence=[T.SKY, T.PURPLE], labels={"value": "%", "season": "", "variable": ""})
            show(T.style(fig, "Season: delay vs cancel rate", 380))

    md(T.section("Daily timeline"))
    tmetric = st.radio("Daily metric", ["Cancellation rate (%)", "Delay rate (%)"], horizontal=True)
    tcol = "cancel_rate_pct" if tmetric.startswith("Cancel") else "delay_rate_pct"
    daily = D.group(f, ("fl_date",)).sort_values("fl_date")
    daily["roll7"] = daily[tcol].rolling(7, min_periods=1).mean()
    fig = go.Figure()
    fig.add_scatter(x=daily["fl_date"], y=daily[tcol], mode="lines", name="Daily", line=dict(color=T.SKY_LIGHT, width=1.5))
    fig.add_scatter(x=daily["fl_date"], y=daily["roll7"], mode="lines", name="7-day average", line=dict(color=T.NAVY, width=3))
    top = daily.sort_values(tcol, ascending=False).head(5)
    fig.add_scatter(x=top["fl_date"], y=top[tcol], mode="markers+text", name="Top 5 days", text=top["fl_date"].dt.strftime("%d %b"),
                    textposition="top center", marker=dict(color=T.ALERT, size=11))
    fig.update_layout(yaxis_title=tmetric)
    show(T.style(fig, f"{tmetric} by day, spikes are event-driven", 440))


# --------------------------------------------------------------------------- 5. delay anatomy
CAUSE_BY = {"Hour of day": "scheduled_dep_hour", "Month": "month", "Airline": "airline_name", "Part of day": "dep_daypart"}


def page_anatomy(f: D.Filters) -> None:
    begin()
    if not need_data(f):
        return
    k, b = D.kpis(f), D.baseline_kpis()
    thr = D.RULES["delay_threshold_minutes"]
    cards([
        T.kpi_card("Late dep → late arr", f"{k['dep_late_arr_late_pct']:.1f}%", f"of flights leaving ≥ {thr} min late", T.ALERT,
                   k["dep_late_arr_late_pct"] - b["dep_late_arr_late_pct"], delta_unit=" pp"),
        T.kpi_card("On-time dep → late arr", f"{k['dep_ok_arr_late_pct']:.1f}%", "delay created en route", T.AMBER,
                   k["dep_ok_arr_late_pct"] - b["dep_ok_arr_late_pct"], delta_unit=" pp"),
        T.kpi_card("Recovered in air", f"{k['avg_minutes_recovered']:.1f} min", "avg, by late departures", T.TEAL,
                   k["avg_minutes_recovered"] - b["avg_minutes_recovered"], good_when_lower=False, delta_unit=" min"),
        T.kpi_card("Late arr, on-time dep", f"{k['arr_late_left_on_time_pct']:.1f}%", "late arrivals that left on time", T.SKY),
    ])

    with safe("cause chart"):
        md(T.section("Cause mix, and the cascade effect"))
        by_label = st.radio("Break delay minutes down by", list(CAUSE_BY), horizontal=True, index=0)
        cz = D.causes(f, CAUSE_BY[by_label])
        xcol = CAUSE_BY[by_label]
        if by_label == "Month":
            cz = cz.assign(**{xcol: cz[xcol].map(mo)})
        elif by_label == "Part of day":
            cz = cz.set_index(xcol).reindex([x for x in D.RULES["daypart_labels"] if x in set(cz[xcol].astype(str))]).reset_index()
        horizontal = by_label == "Airline"
        fig = px.bar(cz, x=["Carrier", "Weather", "NAS", "Security", "Late Aircraft"] if horizontal else xcol,
                     y=xcol if horizontal else ["Carrier", "Weather", "NAS", "Security", "Late Aircraft"],
                     orientation="h" if horizontal else "v", color_discrete_map=T.CAUSE_COLORS,
                     labels={"value": "% of delay minutes", "variable": "Cause", xcol: ""})
        show(T.style(fig, f"Delay-cause mix by {by_label.lower()} (100% = delay minutes of flights ≥ {thr} min late)", 460))
        if by_label == "Hour of day" and {6, 20} <= set(cz[xcol]):
            r = cz.set_index(xcol)
            md(T.note(f"<b class='k'>Cascade evidence</b> · the late-aircraft share rises from <b>{r.loc[6, 'Late Aircraft']:.0f}%</b> "
                      f"(06:00 departures) to <b>{r.loc[20, 'Late Aircraft']:.0f}%</b> (20:00): early delays propagate down each aircraft's day."))

    with safe("section"):
        md(T.section("Distribution, outliers and carry-over"))
        c1, c2 = st.columns(2)
        with c1:
            hist_dep, hist_arr = D.histogram(f, "dep_delay"), D.histogram(f, "arr_delay")
            logy = st.toggle("Log scale (see the tail)", value=False)
            fig = go.Figure()
            fig.add_bar(x=hist_dep["minutes"], y=hist_dep["flights"], name="Departure delay", marker_color=T.SKY, opacity=0.65)
            fig.add_bar(x=hist_arr["minutes"], y=hist_arr["flights"], name="Arrival delay", marker_color=T.ALERT, opacity=0.65)
            fig.update_layout(barmode="overlay", xaxis_title="Minutes (clipped to -60 / +240)", yaxis_title="Flights",
                              yaxis_type="log" if logy else "linear")
            show(T.style(fig, "Most flights are on time; the right tail is long", 420))
        with c2:
            vals = pd.DataFrame({"stat": ["Median", "Mean (winsorized)", "Mean (raw)", "90th percentile"],
                                 "minutes": [k["median_arr_delay_min"], k["avg_arr_delay_winsorized_min"], k["avg_arr_delay_min"], k["p90_arr_delay_min"]]})
            fig = px.bar(vals, x="stat", y="minutes", text="minutes", color="stat", labels={"stat": "", "minutes": "Arrival delay (min)"},
                         color_discrete_sequence=[T.GOOD, T.TEAL, T.AMBER, T.ALERT])
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
            fig.update_layout(showlegend=False)
            show(T.style(fig, "Why one average is not enough", 420))
            md(T.note(f"Raw mean {k['avg_arr_delay_min']:.1f} vs winsorized {k['avg_arr_delay_winsorized_min']:.1f} min: "
                      "extreme delays inflate averages. The sidebar toggles let you winsorize or drop them.", "sky"))

        c1, c2 = st.columns(2)
        with c1:
            sm = D.sample(f)
            fig = px.scatter(sm, x="dep_delay", y="arr_delay", color="haul", opacity=0.4, render_mode="webgl",
                             color_discrete_sequence=[T.SKY, T.AMBER, T.ALERT], labels={"dep_delay": "Departure delay (min)", "arr_delay": "Arrival delay (min)"})
            fig.update_xaxes(range=[-30, 300])
            fig.update_yaxes(range=[-60, 300])
            show(T.style(fig, "Departure vs arrival delay (20k sample)", 440))
        with c2:
            cm = D.correlations(f)
            fig = px.imshow(cm, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto")
            show(T.style(fig, "Correlation of delay drivers", 440))


# --------------------------------------------------------------------------- 6. cancellations & events
def page_cancellations(f: D.Filters) -> None:
    begin()
    if not need_data(f):
        return
    k = D.kpis(f)
    rs = D.cancel_reasons(f)
    daily = D.group(f, ("fl_date",)).sort_values("fl_date")
    ev = daily[daily["flights"] >= 100].sort_values("cancel_rate_pct", ascending=False).head(10)
    share = 100 * ev["cancelled"].sum() / max(int(D.get_filtered(f)["cancelled"].sum()), 1)
    cards([
        T.kpi_card("Cancelled flights", f"{int(D.get_filtered(f)['cancelled'].sum()):,}", f"{k['cancel_rate_pct']:.2f}% of flights", T.PURPLE),
        T.kpi_card("Leading reason", str(rs.iloc[0]["cancellation_reason"]) if len(rs) else "n/a",
                   f"{rs.iloc[0]['share_pct']:.0f}% of cancellations" if len(rs) else "", T.TEAL),
        T.kpi_card("Worst 10 days", f"{share:.0f}%", "of all cancellations", T.ALERT),
        T.kpi_card("Diverted flights", f"{k['diverted_rate_pct']:.2f}%", "landed elsewhere", T.AMBER),
    ])

    with safe("chart"):
        c1, c2 = st.columns([1, 1.5])
        with c1:
            if len(rs):
                fig = px.pie(rs, names="cancellation_reason", values="flights", hole=0.55,
                             color="cancellation_reason", color_discrete_map={"Weather": T.TEAL, "Carrier": T.SKY, "National Air System": T.AMBER, "Security": T.PURPLE})
                fig.update_traces(textinfo="percent")
                fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center"))
                show(T.style(fig, "Why flights are cancelled", 420))
        with c2:
            p = D.pivot(f, "airline_name", "month", "cancelled", 100)
            p.columns = [mo(c) for c in p.columns]
            fig = px.imshow(p, aspect="auto", color_continuous_scale=SCALE, text_auto=".1f", labels=dict(color="Cancel %", x="", y=""))
            show(T.style(fig, "Cancellation rate (%): airline × month", 420))

    md(T.section("Disruption days: the departure board"))
    board = pd.DataFrame({"Date": ev["fl_date"].dt.strftime("%a %d %b %Y"), "Flights": ev["flights"].astype(int),
                          "Cancelled": ev["cancelled"].astype(int), "Cancel %": ev["cancel_rate_pct"].round(1), "Delay %": ev["delay_rate_pct"].round(1)})
    md(T.board_table(board, "Worst days by cancellation rate", hot_col="Cancel %", hot_threshold=5))
    md(T.note(f"The 10 worst days account for <b>{share:.0f}%</b> of all cancellations in this selection: cancellations are driven by "
              "rare events (storms, system outages), not a steady drip. The dataset cannot tell us the cause of an event, only its footprint.", "red"))

    md(T.section("Drill into a day"))
    dmin, dmax = D.load_data()["fl_date"].min().date(), D.load_data()["fl_date"].max().date()
    default = ev.iloc[0]["fl_date"].date() if len(ev) else dmin
    day = st.date_input("Pick a date", value=default, min_value=dmin, max_value=dmax)
    det = D.day_detail(f, str(day))
    if not det:
        st.info("No flights on that day for the current filters.")
        return
    dk = det["kpis"]
    cards([
        T.kpi_card("Flights that day", f"{dk['total_flights']:,}", "", T.SKY),
        T.kpi_card("Cancelled", f"{dk['cancel_rate_pct']:.1f}%", "", T.PURPLE, dk["cancel_rate_pct"] - k["cancel_rate_pct"], delta_unit=" pp"),
        T.kpi_card("Delayed", f"{dk['delay_rate_pct']:.1f}%", "", T.ALERT, dk["delay_rate_pct"] - k["delay_rate_pct"], delta_unit=" pp"),
        T.kpi_card("Avg arrival delay", f"{dk['avg_arr_delay_min']:.0f} min", "", T.AMBER),
    ])
    c1, c2 = st.columns(2)
    with c1:
        a = det["airlines"].head(8).sort_values("cancel_rate_pct")
        fig = px.bar(a, x="cancel_rate_pct", y="airline_name", orientation="h", color="cancel_rate_pct", color_continuous_scale=SCALE,
                     text="cancel_rate_pct", labels={"cancel_rate_pct": "Cancel rate (%)", "airline_name": ""})
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
        fig.update_layout(coloraxis_showscale=False)
        show(T.style(fig, "Airlines most affected that day", 380))
    with c2:
        hh = det["hours"].sort_values("scheduled_dep_hour")
        fig = go.Figure()
        fig.add_bar(x=hh["scheduled_dep_hour"], y=hh["cancel_rate_pct"], name="Cancel rate (%)", marker_color=T.PURPLE)
        fig.add_scatter(x=hh["scheduled_dep_hour"], y=hh["delay_rate_pct"], name="Delay rate (%)", mode="lines+markers", line=dict(color=T.ALERT, width=3))
        fig.update_layout(xaxis_title="Scheduled departure hour", yaxis_title="%")
        show(T.style(fig, "How the day unfolded", 380))


# --------------------------------------------------------------------------- 7. route finder
def page_route(f: D.Filters) -> None:
    begin()
    if not need_data(f):
        return
    names = D.airport_names()
    o = D.group(f, ("origin_label",), 50).sort_values("flights", ascending=False)
    labels = o["origin_label"].astype(str).tolist()
    if not labels:
        st.info("No airport has enough flights (≥ 50) in this selection to look up a route. Widen the filters.")
        return
    c1, c2 = st.columns(2)
    default = labels.index("ATL (Atlanta)") if "ATL (Atlanta)" in labels else 0
    origin_lab = c1.selectbox("From", labels, index=default)
    origin = origin_lab.split(" ")[0]
    dests = D.dest_options(f, origin)
    if not dests:
        st.info("No destinations for this origin with the current filters.")
        return
    dest = c2.selectbox("To", dests, format_func=lambda c: names.get(c, c))
    det = D.route_detail(f, origin, dest)
    if not det:
        st.info("No flights on this route with the current filters.")
        return
    k, b = det["kpis"], D.baseline_kpis()
    arr_key = "avg_arr_delay_winsorized_min" if f.winsor else "avg_arr_delay_min"
    md(T.section(f"{origin} → {dest}"))
    cards([
        T.kpi_card("Flights in sample", f"{det['flights']:,}", "1 in ~7 of all flights", T.SKY),
        T.kpi_card("On-time arrivals", f"{k['ontime_pct']:.1f}%", "", T.GOOD, k["ontime_pct"] - b["ontime_pct"], good_when_lower=False, delta_unit=" pp"),
        T.kpi_card("Cancelled", f"{k['cancel_rate_pct']:.2f}%", "", T.PURPLE, k["cancel_rate_pct"] - b["cancel_rate_pct"], delta_fmt="{:+.2f}", delta_unit=" pp"),
        T.kpi_card("Avg arrival delay", f"{k[arr_key]:.1f} min", f"median {k['median_arr_delay_min']:.0f}", T.AMBER, k[arr_key] - b[arr_key], delta_unit=" min"),
        T.kpi_card("90th-pct delay", f"{k['p90_arr_delay_min']:.0f} min", "", T.ALERT),
    ])
    if det["flights"] < 100:
        md(T.note(f"Only <b>{det['flights']}</b> sampled flights on this route: percentages are very uncertain.", "red"))

    c1, c2 = st.columns(2)
    with c1:
        a = det["airlines"].sort_values("delay_rate_pct")
        fig = px.bar(a, x="delay_rate_pct", y="airline_name", orientation="h", text="flights", color="delay_rate_pct", color_continuous_scale=SCALE,
                     labels={"delay_rate_pct": "Delay rate (%)", "airline_name": ""})
        fig.update_traces(texttemplate="%{text} flights", textposition="outside", cliponaxis=False)
        fig.update_layout(coloraxis_showscale=False)
        show(T.style(fig, "Airlines on this route", 360))
    with c2:
        hh = det["hours"].sort_values("scheduled_dep_hour")
        fig = px.bar(hh, x="scheduled_dep_hour", y="delay_rate_pct", color="delay_rate_pct", color_continuous_scale=SCALE,
                     labels={"scheduled_dep_hour": "Scheduled departure hour", "delay_rate_pct": "Delay rate (%)"})
        fig.update_layout(coloraxis_showscale=False)
        show(T.style(fig, "Best and worst departure hours on this route", 360))
    mm = det["months"].sort_values("month")
    fig = go.Figure()
    fig.add_bar(x=[mo(m) for m in mm["month"]], y=mm["delay_rate_pct"], name="Delay rate (%)", marker_color=T.SKY)
    fig.add_scatter(x=[mo(m) for m in mm["month"]], y=mm["cancel_rate_pct"], name="Cancel rate (%)", mode="lines+markers", line=dict(color=T.ALERT, width=3))
    show(T.style(fig, "Month by month", 340))


# --------------------------------------------------------------------------- 8. about
def page_about(f: D.Filters) -> None:
    begin()
    thr = D.RULES["delay_threshold_minutes"]
    md(T.section("The business problem"))
    md(T.note("<b class='k'>How can an airline reduce arrival delays and cancellations</b> by identifying which causes, carriers, airports, "
              "routes and time windows generate the most disruption, and which of those it can actually control?", "sky"))
    st.markdown("""
**Who uses this:** Network Operations (where/when to add buffer), Schedule Planning (which banks to re-time), Station Managers
(ground-handling bottlenecks), Customer Experience (who to re-accommodate) and benchmark analysts (fair airline comparison).
""")
    md(T.section("How to read the numbers"))
    st.markdown(f"""
| Metric | Definition |
|---|---|
| **Delay rate** | completed flights arriving ≥ **{thr} min** late ÷ completed flights (US DOT standard) |
| **On-time %** | 100 − delay rate |
| **Cancel / diversion rate** | cancelled (diverted) ÷ all scheduled flights; never counted as "on time" |
| **P90 delay** | 90th-percentile arrival delay: what a customer on a bad day experiences |
| **Winsorized mean** | average after capping delays at the 0.5 / 99.5 percentile, so a few multi-day delays cannot dominate rankings |
| **Extreme delay** | arrival ≥ **{D.CFG['outliers']['extreme_delay_minutes']} min** (6 h) late. Flagged, never deleted |
| **Cause share** | delay minutes per cause ÷ total, among flights delayed ≥ {thr} min |
""")
    md(T.section("Using the sidebar"))
    st.markdown("""
* **Filters** (airline, months, weekday, part of day, haul, origin airport) apply to **every page**; KPI cards show the change *vs the full network*.
* **Exclude extreme delays** removes flights ≥ 6 h late from all numbers; **Winsorized averages** switches averages between robust and raw.
* Every table has a CSV download; charts are fully interactive (hover, zoom, legend toggle).
""")
    md(T.section("Data & quality"))
    qp = D.ROOT / D.CFG["paths"]["data_quality_report"]
    if qp.exists():
        q = json.loads(qp.read_text(encoding="utf-8"))
        o = q.get("outliers", {})
        st.markdown(f"""
* **{q['rows_clean']:,}** flights (random sample of ~7M US domestic flights, 2024) · {q['cancelled_flights']:,} cancelled · {q['diverted_flights']:,} diverted
* Delay-cause minutes that do not reconcile with arrival delay: **{q.get('delay_cause_sum_mismatch_pct', 'n/a')}%**
* Extreme delays: **{o.get('extreme_delay_flights', 'n/a'):,}** flights, **{o.get('extreme_delay_share_of_positive_delay_minutes_pct', 'n/a')}%** of positive delay minutes; longest **{o.get('max_arr_delay_min', 0):,.0f} min**
""")
    md(T.section("What this dashboard cannot tell you"))
    st.markdown("""
* **Association, not causation**, and no prediction model.
* **Airline comparisons are not mix-adjusted** (airports, routes, hours differ by airline).
* **Sample of ~1 in 7 flights**: small airports and routes are noisy. Rankings enforce minimum flight counts.
* **No tail number, weather, capacity, passenger or cost data**: aircraft chains and dollar impact cannot be derived.
* **One year (2024)**: event explanations (e.g. a July spike) are inferred from patterns, not in the data.
* **Map coordinates are approximate** and cover the busiest airports only.

See `FINDINGS.md` in the repository for the full findings, recommendations and roadmap.
""")
