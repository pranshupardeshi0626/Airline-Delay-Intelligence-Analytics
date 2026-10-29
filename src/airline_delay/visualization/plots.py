"""Plotly figure factory.

Every function takes already-aggregated tables (or the cleaned frame for
distribution plots) and returns a ``plotly.graph_objects.Figure``. Nothing is
shown or saved here - ``save_figures`` handles persistence - so the same
figures can be embedded in a notebook, a report or a Streamlit/Dash app.

Chart-choice rules applied (fixes versus the original notebook)
---------------------------------------------------------------
* No pie/donut for non-additive quantities (e.g. 'average delay by day type').
* Bars for rankings, heatmaps for two-way patterns, stacked 100 % bars for mix.
* Rankings only include groups above a minimum sample size.
* Heavy scatter/box/violin plots use a reproducible random sample.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from airline_delay.analysis import metrics as m
from airline_delay.data.cleaning import completed_mask
from airline_delay.logging_utils import get_logger

log = get_logger(__name__)


def _style(fig: go.Figure, cfg: Dict[str, Any], title: str, height: int = 520) -> go.Figure:
    """Apply the shared look & feel to every figure."""
    fig.update_layout(template=cfg["visualization"]["template"], title=dict(text=title, x=0.02),
                      height=height, margin=dict(l=60, r=30, t=70, b=60))
    return fig


def _sample(df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    """Reproducible sample so heavy charts stay light and deterministic."""
    v = cfg["visualization"]
    return df.sample(min(len(df), v["scatter_sample_size"]), random_state=v["random_state"])


# ----------------------------- 1. Volume / distribution --------------------- #
def fig_airline_volume(t: Dict[str, pd.DataFrame], cfg) -> go.Figure:
    """Flight volume by airline (market share of scheduled flights)."""
    d = t["airline_kpis"].sort_values("flights")
    f = px.bar(d, x="flights", y="airline_name", orientation="h", text="flights",
               labels={"flights": "Scheduled flights", "airline_name": ""})
    f.update_traces(marker_color="#2a6fdb", textposition="outside")
    return _style(f, cfg, "Flight volume by airline")


def fig_monthly_volume(t, cfg) -> go.Figure:
    """Monthly flight counts - confirms whether the sample is seasonally balanced."""
    d = t["month_kpis"]
    f = px.bar(d, x="month", y="flights", labels={"month": "Month", "flights": "Flights"})
    f.update_traces(marker_color="#2a6fdb")
    f.update_xaxes(dtick=1)
    return _style(f, cfg, "Flights per month")


def fig_status_mix(df: pd.DataFrame, cfg) -> go.Figure:
    """Arrival-status mix across the network."""
    c = df["arrival_status"].value_counts().rename_axis("status").reset_index(name="flights")
    c["share_pct"] = (100 * c["flights"] / c["flights"].sum()).round(2)
    f = px.bar(c, x="status", y="flights", text="share_pct", color="status",
               labels={"status": "", "flights": "Flights"})
    f.update_traces(texttemplate="%{text}%", textposition="outside")
    f.update_layout(showlegend=False)
    return _style(f, cfg, "Arrival status distribution")


def fig_delay_histograms(df: pd.DataFrame, cfg) -> go.Figure:
    """Distribution of departure/arrival delay, clipped to [-60, 240] so outliers don't hide the shape.

    Values are pre-binned with NumPy (5-minute bins) and drawn as bars: embedding ~1M raw points in an HTML
    histogram produced a 21 MB file; binned bars are a few KB and look identical.
    """
    done = df[completed_mask(df)]
    edges = np.arange(-60, 245, 5)
    f = go.Figure()
    for col, name, colour in (("dep_delay", "Departure delay", "#2a6fdb"), ("arr_delay", "Arrival delay", "#e4572e")):
        counts, _ = np.histogram(done[col].astype(float).clip(-60, 240).dropna(), bins=edges)
        f.add_trace(go.Bar(x=edges[:-1] + 2.5, y=counts, name=name, opacity=0.6, marker_color=colour))
    f.update_layout(barmode="overlay", xaxis_title="Minutes (clipped to -60 / +240)", yaxis_title="Flights")
    return _style(f, cfg, "Delay distributions (completed flights)")


def fig_hourly_volume(t, cfg) -> go.Figure:
    """Scheduled departures by hour - the demand profile of the network."""
    f = px.bar(t["hour_kpis"], x="scheduled_dep_hour", y="flights",
               labels={"scheduled_dep_hour": "Scheduled departure hour", "flights": "Flights"})
    f.update_traces(marker_color="#2a6fdb")
    f.update_xaxes(dtick=1)
    return _style(f, cfg, "Scheduled departures by hour of day")


# ----------------------------- 2. Airline performance ----------------------- #
def fig_airline_scorecard(t, cfg) -> go.Figure:
    """Airline reliability map: delay rate vs cancellation rate (bubble = volume)."""
    d = t["airline_kpis"]
    f = px.scatter(d, x="delay_rate_pct", y="cancel_rate_pct", size="flights", text="airline_name",
                   labels={"delay_rate_pct": "Delay rate (% of completed flights >=15 min late)",
                           "cancel_rate_pct": "Cancellation rate (%)"})
    f.update_traces(textposition="top center", marker=dict(color="#2a6fdb", opacity=0.7))
    f.add_vline(x=d["delay_rate_pct"].median(), line_dash="dot", line_color="grey")
    f.add_hline(y=d["cancel_rate_pct"].median(), line_dash="dot", line_color="grey")
    return _style(f, cfg, "Airline reliability scorecard (dotted lines = airline median)", 600)


def fig_airline_dep_delay(t, cfg) -> go.Figure:
    """Average departure delay by airline (ranked)."""
    d = t["airline_kpis"].sort_values("avg_dep_delay_w", ascending=False)
    f = px.bar(d, x="airline_name", y="avg_dep_delay_w", text="avg_dep_delay_w",
               labels={"airline_name": "", "avg_dep_delay_w": "Avg departure delay, winsorized (min)"})
    f.update_traces(marker_color="#e4572e", textposition="outside")
    return _style(f, cfg, "Average departure delay by airline")


def fig_airline_arr_box(df: pd.DataFrame, cfg) -> go.Figure:
    """Arrival-delay spread per airline (sampled; y clipped to keep boxes readable)."""
    s = _sample(df[completed_mask(df)], cfg).copy()
    s["arr_delay"] = s["arr_delay"].astype(float).clip(-60, 240)
    f = px.box(s, x="airline_name", y="arr_delay", labels={"airline_name": "", "arr_delay": "Arrival delay (min, clipped)"})
    return _style(f, cfg, "Arrival delay distribution by airline", 560)


# ----------------------------- 3. Airports & routes ------------------------- #
def _hbar(d: pd.DataFrame, x: str, y: str, title: str, xlabel: str, cfg, colour: str, n: int = 15) -> go.Figure:
    """Shared horizontal ranking bar used by airport/route charts."""
    d = d.sort_values(x, ascending=False).head(n).sort_values(x)
    f = px.bar(d, x=x, y=y, orientation="h", text=x, labels={x: xlabel, y: ""})
    f.update_traces(marker_color=colour, textposition="outside")
    return _style(f, cfg, title, 560)


def fig_airport_dep_delay(t, cfg):
    """Origin airports with the highest average departure delay."""
    return _hbar(t["airport_kpis"], "avg_dep_delay_w", "origin_label",
                 f"Top 15 origin airports by avg departure delay (>= {cfg['business_rules']['min_flights_airport']} flights)",
                 "Avg departure delay, winsorized (min)", cfg, "#e4572e")


def fig_airport_cancel(t, cfg):
    """Origin airports with the highest cancellation rate."""
    return _hbar(t["airport_kpis"], "cancel_rate_pct", "origin_label",
                 f"Top 15 origin airports by cancellation rate (>= {cfg['business_rules']['min_flights_airport']} flights)",
                 "Cancellation rate (%)", cfg, "#7b2cbf")


def fig_dest_arr_delay(t, cfg):
    """Destination airports with the highest average arrival delay."""
    return _hbar(t["dest_airport_kpis"], "avg_arr_delay_w", "dest_label",
                 f"Top 15 destination airports by avg arrival delay (>= {cfg['business_rules']['min_flights_airport']} flights)",
                 "Avg arrival delay, winsorized (min)", cfg, "#f18f01")


def fig_route_arr_delay(t, cfg):
    """Routes with the highest average arrival delay."""
    return _hbar(t["route_kpis"], "avg_arr_delay_w", "route",
                 f"Top 15 routes by avg arrival delay (>= {cfg['business_rules']['min_flights_route']} flights)",
                 "Avg arrival delay, winsorized (min)", cfg, "#008080")


# ----------------------------- 4. Time patterns ----------------------------- #
def fig_hourly_delay(t, cfg) -> go.Figure:
    """Average departure delay and cancellation rate by scheduled hour (dual axis)."""
    d = t["hour_kpis"]
    f = go.Figure()
    f.add_trace(go.Scatter(x=d["scheduled_dep_hour"], y=d["avg_dep_delay_w"], mode="lines+markers",
                           name="Avg departure delay, winsorized (min)", line=dict(color="#e4572e", width=3)))
    f.add_trace(go.Bar(x=d["scheduled_dep_hour"], y=d["cancel_rate_pct"], name="Cancellation rate (%)",
                       marker_color="rgba(123,44,191,0.35)", yaxis="y2"))
    f.update_layout(xaxis=dict(title="Scheduled departure hour", dtick=1), yaxis=dict(title="Avg departure delay, winsorized (min)"),
                    yaxis2=dict(title="Cancellation rate (%)", overlaying="y", side="right", showgrid=False))
    return _style(f, cfg, "Delay builds through the day (cascading delays)")


def fig_monthly_delay(t, cfg) -> go.Figure:
    """Delay rate and cancellation rate by month."""
    d = t["month_kpis"]
    f = go.Figure()
    f.add_trace(go.Bar(x=d["month"], y=d["delay_rate_pct"], name="Delay rate (%)", marker_color="#e4572e"))
    f.add_trace(go.Scatter(x=d["month"], y=d["cancel_rate_pct"], name="Cancellation rate (%)",
                           mode="lines+markers", line=dict(color="#7b2cbf", width=3), yaxis="y2"))
    f.update_layout(xaxis=dict(title="Month", dtick=1), yaxis=dict(title="Delay rate (%)"),
                    yaxis2=dict(title="Cancellation rate (%)", overlaying="y", side="right", showgrid=False))
    return _style(f, cfg, "Seasonality of delays and cancellations")


def fig_day_type(t, cfg) -> go.Figure:
    """Weekday vs weekend reliability (bars, because the quantities are rates not shares)."""
    d = t["daytype_kpis"].melt(id_vars="day_type", value_vars=["delay_rate_pct", "cancel_rate_pct"],
                               var_name="metric", value_name="pct")
    d["metric"] = d["metric"].map({"delay_rate_pct": "Delay rate", "cancel_rate_pct": "Cancellation rate"})
    f = px.bar(d, x="day_type", y="pct", color="metric", barmode="group", text="pct",
               labels={"day_type": "", "pct": "%"})
    f.update_traces(textposition="outside")
    return _style(f, cfg, "Weekday vs weekend reliability")


def fig_heatmap_month_hour(df: pd.DataFrame, cfg) -> go.Figure:
    """High-risk windows: average departure delay by month x scheduled hour."""
    p = m.pivot_metric(df, "month", "scheduled_dep_hour", "dep_delay")
    f = px.imshow(p, aspect="auto", color_continuous_scale="RdYlBu_r", text_auto=".0f",
                  labels=dict(x="Scheduled departure hour", y="Month", color="Avg delay (min)"))
    return _style(f, cfg, "Average departure delay: month x hour", 620)


def fig_heatmap_dow_hour(df: pd.DataFrame, cfg) -> go.Figure:
    """Weekly rhythm: delay rate (%) by day of week x scheduled hour."""
    p = m.pivot_metric(df, "day_name", "scheduled_dep_hour", "is_arr_delayed", scale=100)
    p = p.reindex([cfg["lookups"]["day_names"][i] for i in range(1, 8)])
    f = px.imshow(p, aspect="auto", color_continuous_scale="YlOrRd", text_auto=".0f",
                  labels=dict(x="Scheduled departure hour", y="Day", color="Delay rate %"))
    return _style(f, cfg, "Delay rate (%): weekday x hour", 480)


def fig_heatmap_airline_month_cancel(df: pd.DataFrame, cfg) -> go.Figure:
    """Cancellation rate (%) by airline x month."""
    p = m.pivot_metric(df, "airline_name", "month", "cancelled", scale=100)
    f = px.imshow(p, aspect="auto", color_continuous_scale="Inferno", text_auto=".1f",
                  labels=dict(x="Month", y="", color="Cancel %"))
    return _style(f, cfg, "Cancellation rate (%): airline x month", 600)


# ----------------------------- 5. Causes & relationships -------------------- #
def fig_cause_share(t, cfg) -> go.Figure:
    """Network-wide share of delay minutes by cause."""
    d = t["delay_causes"].sort_values("share_pct")
    f = px.bar(d, x="share_pct", y="cause", orientation="h", text="share_pct",
               labels={"share_pct": "Share of delay minutes (%)", "cause": ""})
    f.update_traces(marker_color="#2a6fdb", textposition="outside")
    return _style(f, cfg, "What causes delay minutes? (flights delayed >= 15 min)", 420)


def _stacked_share(d: pd.DataFrame, x: str, cfg, title: str) -> go.Figure:
    """100 % stacked bars of cause mix."""
    cols = ["Carrier", "Weather", "NAS", "Security", "Late Aircraft"]
    f = px.bar(d, x=x, y=cols, barmode="stack", labels={"value": "% of delay minutes", "variable": "Cause"},
               color_discrete_sequence=px.colors.qualitative.Bold)
    return _style(f, cfg, title, 560)


def fig_cause_by_airline(t, cfg):
    """Delay-cause mix per airline."""
    return _stacked_share(t["delay_causes_by_airline"], "airline_name", cfg, "Delay-cause mix by airline")


def fig_cause_by_month(t, cfg):
    """Delay-cause mix per month."""
    f = _stacked_share(t["delay_causes_by_month"], "month", cfg, "Delay-cause mix by month")
    f.update_xaxes(dtick=1)
    return f


def fig_cancel_reasons(t, cfg) -> go.Figure:
    """Cancellation reasons (BTS codes A-D)."""
    d = t["cancellation_reasons"]
    f = px.bar(d, x="cancellation_reason", y="flights", text="share_pct",
               labels={"cancellation_reason": "", "flights": "Cancelled flights"})
    f.update_traces(texttemplate="%{text}%", marker_color="#7b2cbf", textposition="outside")
    return _style(f, cfg, "Why are flights cancelled?", 460)


def fig_delay_severity(t, cfg) -> go.Figure:
    """The outlier story: share of delayed flights vs share of delay minutes by severity bucket."""
    d = t["delay_severity"].melt(id_vars="severity", value_vars=["pct_of_delayed_flights", "pct_of_delay_minutes"],
                                 var_name="metric", value_name="pct")
    d["metric"] = d["metric"].map({"pct_of_delayed_flights": "% of delayed flights", "pct_of_delay_minutes": "% of delay minutes"})
    f = px.bar(d, x="severity", y="pct", color="metric", barmode="group", text="pct",
               labels={"severity": "Arrival delay severity", "pct": "%"})
    f.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    return _style(f, cfg, "A few extreme delays carry a disproportionate share of delay minutes", 480)


def fig_daily_cancellations(t, cfg) -> go.Figure:
    """Daily cancellation rate: shows that cancellations are driven by a few event days, not a steady drip."""
    d = t["daily_kpis"].copy()
    d["fl_date"] = pd.to_datetime(d["fl_date"])
    f = px.line(d, x="fl_date", y="cancel_rate_pct", labels={"fl_date": "", "cancel_rate_pct": "Cancelled flights (%)"})
    f.update_traces(line=dict(color="#7b2cbf", width=1.5))
    for _, r in t["disruption_days"].head(5).iterrows():
        f.add_annotation(x=pd.Timestamp(r["fl_date"]), y=r["cancel_rate_pct"], text=pd.Timestamp(r["fl_date"]).strftime("%d %b"),
                         showarrow=True, arrowhead=2, ay=-25)
    return _style(f, cfg, "Daily cancellation rate - a handful of event days drive most cancellations", 480)


def fig_cause_by_hour(t, cfg) -> go.Figure:
    """Delay-cause mix by scheduled hour: late-aircraft share grows through the day (cascade)."""
    f = _stacked_share(t["delay_causes_by_hour"], "scheduled_dep_hour", cfg, "Delay-cause mix by scheduled departure hour")
    f.update_xaxes(dtick=1, title="Scheduled departure hour")
    return f


def fig_dep_vs_arr(df: pd.DataFrame, cfg) -> go.Figure:
    """How much of a departure delay carries through to arrival (sampled scatter)."""
    s = _sample(df[completed_mask(df)], cfg)
    f = px.scatter(s, x="dep_delay", y="arr_delay", opacity=0.35, render_mode="webgl",
                   labels={"dep_delay": "Departure delay (min)", "arr_delay": "Arrival delay (min)"})
    f.update_traces(marker=dict(size=3, color="#2a6fdb"))
    return _style(f, cfg, "Departure delay vs arrival delay (25k sample)")


def fig_recovery_by_haul(df: pd.DataFrame, cfg) -> go.Figure:
    """Time recovered in the air by haul length, for flights that left >= 15 min late."""
    d = df[completed_mask(df) & (df["dep_delay"] >= 15)].copy()
    d["delay_recovered"] = d["delay_recovered"].astype(float)
    g = d.groupby("haul", observed=True)["delay_recovered"].mean().reset_index()
    f = px.bar(g, x="haul", y="delay_recovered", text=g["delay_recovered"].round(1),
               labels={"haul": "", "delay_recovered": "Avg minutes recovered en route"})
    f.update_traces(marker_color="#008080", textposition="outside")
    return _style(f, cfg, "Longer flights recover more of a late departure", 440)


def fig_correlation(df: pd.DataFrame, cfg) -> go.Figure:
    """Correlation of delay drivers."""
    c = m.correlation_matrix(df)
    f = px.imshow(c, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto")
    return _style(f, cfg, "Correlation of delay factors (completed flights)", 700)


# --------------------------------------------------------------------------- #
def generate_all_figures(df: pd.DataFrame, tables: Dict[str, pd.DataFrame], cfg: Dict[str, Any]) -> Dict[str, go.Figure]:
    """Build every figure. Keys become the HTML file names."""
    return {
        "01_airline_volume": fig_airline_volume(tables, cfg),
        "02_monthly_volume": fig_monthly_volume(tables, cfg),
        "03_arrival_status_mix": fig_status_mix(df, cfg),
        "04_delay_distributions": fig_delay_histograms(df, cfg),
        "05_hourly_volume": fig_hourly_volume(tables, cfg),
        "06_airline_scorecard": fig_airline_scorecard(tables, cfg),
        "07_airline_dep_delay": fig_airline_dep_delay(tables, cfg),
        "08_airline_arr_delay_box": fig_airline_arr_box(df, cfg),
        "09_airport_dep_delay": fig_airport_dep_delay(tables, cfg),
        "10_airport_cancel_rate": fig_airport_cancel(tables, cfg),
        "11_dest_arr_delay": fig_dest_arr_delay(tables, cfg),
        "12_route_arr_delay": fig_route_arr_delay(tables, cfg),
        "13_hourly_delay": fig_hourly_delay(tables, cfg),
        "14_monthly_delay": fig_monthly_delay(tables, cfg),
        "15_weekday_vs_weekend": fig_day_type(tables, cfg),
        "16_heatmap_month_hour": fig_heatmap_month_hour(df, cfg),
        "17_heatmap_dow_hour": fig_heatmap_dow_hour(df, cfg),
        "18_heatmap_airline_month_cancel": fig_heatmap_airline_month_cancel(df, cfg),
        "19_delay_cause_share": fig_cause_share(tables, cfg),
        "20_delay_cause_by_airline": fig_cause_by_airline(tables, cfg),
        "21_delay_cause_by_month": fig_cause_by_month(tables, cfg),
        "22_cancellation_reasons": fig_cancel_reasons(tables, cfg),
        "23_dep_vs_arr_delay": fig_dep_vs_arr(df, cfg),
        "24_recovery_by_haul": fig_recovery_by_haul(df, cfg),
        "25_correlation": fig_correlation(df, cfg),
        "26_delay_severity": fig_delay_severity(tables, cfg),
        "27_daily_cancellations": fig_daily_cancellations(tables, cfg),
        "28_delay_cause_by_hour": fig_cause_by_hour(tables, cfg),
    }


def save_figures(figs: Dict[str, go.Figure], out_dir: str | Path) -> None:
    """Write each figure as a standalone interactive HTML file (plotly.js loaded from CDN)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, fig in figs.items():
        fig.write_html(out_dir / f"{name}.html", include_plotlyjs="cdn")
    log.info("Saved %d figures -> %s", len(figs), out_dir)
