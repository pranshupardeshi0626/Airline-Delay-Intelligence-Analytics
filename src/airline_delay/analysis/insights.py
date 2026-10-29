"""Turns KPI tables into (a) CSV exports and (b) a data-driven markdown report.

Every number in the report is computed from the data at run time - nothing is
hard-coded - so the narrative can never drift away from the evidence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd

from airline_delay.analysis import metrics as m
from airline_delay.logging_utils import get_logger

log = get_logger(__name__)


def build_tables(df: pd.DataFrame, cfg: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """Compute every summary table used by the report and the figures."""
    r = cfg["business_rules"]
    tables = {
        "airline_kpis": m.group_kpis(df, "airline_name", cfg, r["min_flights_airline"]),
        "airport_kpis": m.group_kpis(df, "origin_label", cfg, r["min_flights_airport"]),
        "dest_airport_kpis": m.group_kpis(df, "dest_label", cfg, r["min_flights_airport"]),
        "route_kpis": m.group_kpis(df, "route", cfg, r["min_flights_route"]),
        "hour_kpis": m.group_kpis(df, "scheduled_dep_hour", cfg),
        "daily_kpis": m.group_kpis(df, "fl_date", cfg),
        "delay_causes_by_hour": m.delay_cause_summary(df, cfg, by="scheduled_dep_hour"),
        "month_kpis": m.group_kpis(df, "month", cfg),
        "daytype_kpis": m.group_kpis(df, "day_type", cfg),
        "dow_kpis": m.group_kpis(df, "day_of_week", cfg),
        "haul_kpis": m.group_kpis(df, "haul", cfg),
        "delay_severity": m.delay_severity(df, cfg),
        "delay_causes": m.delay_cause_summary(df, cfg),
        "delay_causes_by_airline": m.delay_cause_summary(df, cfg, by="airline_name"),
        "delay_causes_by_month": m.delay_cause_summary(df, cfg, by="month"),
        "cancellation_reasons": m.cancellation_reasons(df),
        "correlations": m.correlation_matrix(df).reset_index(names="variable"),
    }
    tables["disruption_days"] = m.disruption_days(tables["daily_kpis"])
    return tables


def export_tables(tables: Dict[str, pd.DataFrame], out_dir: str | Path) -> None:
    """Write each summary table to ``reports/tables/<name>.csv``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, tbl in tables.items():
        tbl.to_csv(out_dir / f"{name}.csv", index=False)
    log.info("Exported %d tables -> %s", len(tables), out_dir)


def _fmt_table(df: pd.DataFrame, cols: Dict[str, str], n: int = 5) -> str:
    """Render the top-n rows of a DataFrame as a markdown table."""
    sub = df.head(n)[list(cols)].rename(columns=cols)
    header = "| " + " | ".join(sub.columns) + " |\n|" + "---|" * len(sub.columns) + "\n"
    rows = "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in sub.itertuples(index=False))
    return header + rows


def render_report(df: pd.DataFrame, tables: Dict[str, pd.DataFrame], kpis: Dict[str, float],
                  cfg: Dict[str, Any], quality: Dict[str, Any]) -> str:
    """Compose the markdown insight report from computed tables."""
    thr = cfg["business_rules"]["delay_threshold_minutes"]
    air, apt, rte = tables["airline_kpis"], tables["airport_kpis"], tables["route_kpis"]
    hour, month, cause = tables["hour_kpis"], tables["month_kpis"], tables["delay_causes"]
    dtype = tables["daytype_kpis"].set_index("day_type")

    top_cause = cause.sort_values("share_pct", ascending=False).iloc[0]
    worst_hr = hour.sort_values("avg_dep_delay_w", ascending=False).iloc[0]
    best_hr = hour.sort_values("avg_dep_delay_w").iloc[0]
    worst_mo = month.sort_values("delay_rate_pct", ascending=False).iloc[0]
    best_mo = month.sort_values("delay_rate_pct").iloc[0]
    worst_cancel_mo = month.sort_values("cancel_rate_pct", ascending=False).iloc[0]

    lines = [
        "# Airline Delay Intelligence - Auto-generated Insight Report",
        "",
        f"*Dataset: {kpis['total_flights']:,} scheduled flights. Delay = arrival >= {thr} min late (DOT standard).*",
        "",
        "## 1. Network health",
        f"- **On-time performance:** {kpis['ontime_pct']}% of completed flights arrive within {thr} min of schedule "
        f"({kpis['delay_rate_pct']}% are delayed).",
        f"- **Cancellations:** {kpis['cancel_rate_pct']}% | **Diversions:** {kpis['diverted_rate_pct']}%.",
        f"- **Average arrival delay:** {kpis['avg_arr_delay_min']} min (median {kpis['median_arr_delay_min']}); "
        f"90th percentile {kpis['p90_arr_delay_min']} min.",
        f"- When a flight *is* delayed it is late by **{kpis['avg_delay_when_delayed_min']} min** on average, "
        f"accumulating **{int(kpis['total_delay_hours']):,} passenger-flight delay hours** in the sample.",
        f"- **Carry-over:** {kpis.get('dep_late_arr_late_pct', 'n/a')}% of flights that depart >= {thr} min late also arrive late, "
        f"and they recover only {kpis.get('avg_minutes_recovered', 'n/a')} min on average in the air; "
        f"{kpis.get('arr_late_left_on_time_pct', 'n/a')}% of late arrivals actually left on time.",
        "",
        "## 2. What drives delays?",
        f"- **{top_cause['cause']}** is the largest single cause, responsible for **{top_cause['share_pct']}%** of delay minutes.",
        "",
        _fmt_table(cause.sort_values("share_pct", ascending=False),
                   {"cause": "Cause", "share_pct": "Share of delay minutes (%)",
                    "avg_minutes_per_delayed_flight": "Avg min / delayed flight"}, 5),
        "",
        "## 3. Who performs worst? (airlines with enough volume)",
        _fmt_table(air.sort_values("delay_rate_pct", ascending=False),
                   {"airline_name": "Airline", "flights": "Flights", "delay_rate_pct": "Delay rate %",
                    "cancel_rate_pct": "Cancel rate %", "median_arr_delay": "Median arr delay (min)",
                    "avg_arr_delay_w": "Avg arr delay, winsorized (min)"}, 5),
        "",
        f"Best performer on delay rate: **{air.sort_values('delay_rate_pct').iloc[0]['airline_name']}** "
        f"({air['delay_rate_pct'].min()}%).",
        "",
        "## 4. Airport and route bottlenecks",
        f"Origin airports with >= {cfg['business_rules']['min_flights_airport']} flights, ranked by winsorized average departure delay:",
        "",
        _fmt_table(apt.sort_values("avg_dep_delay_w", ascending=False),
                   {"origin_label": "Airport", "flights": "Flights", "avg_dep_delay_w": "Avg dep delay, winsorized (min)",
                    "delay_rate_pct": "Delay rate %", "cancel_rate_pct": "Cancel rate %"}, 5),
        "",
        f"Routes with >= {cfg['business_rules']['min_flights_route']} flights, ranked by winsorized average arrival delay:",
        "",
        _fmt_table(rte.sort_values("avg_arr_delay_w", ascending=False),
                   {"route": "Route", "flights": "Flights", "avg_arr_delay_w": "Avg arr delay, winsorized (min)",
                    "delay_rate_pct": "Delay rate %"}, 5),
        "",
        "## 5. When do disruptions happen?",
        f"- **Hour of day:** average departure delay is lowest at {int(best_hr['scheduled_dep_hour']):02d}:00 "
        f"({best_hr['avg_dep_delay_w']} min) and highest at {int(worst_hr['scheduled_dep_hour']):02d}:00 "
        f"({worst_hr['avg_dep_delay_w']} min) - delays snowball through the day as aircraft rotations run late.",
        f"- **Month:** delay rate peaks in month {int(worst_mo['month'])} ({worst_mo['delay_rate_pct']}%) and is lowest in "
        f"month {int(best_mo['month'])} ({best_mo['delay_rate_pct']}%). "
        f"Cancellations peak in month {int(worst_cancel_mo['month'])} ({worst_cancel_mo['cancel_rate_pct']}%).",
    ]
    if {"Weekday", "Weekend"} <= set(dtype.index):
        lines.append(f"- **Weekday vs weekend:** delay rate {dtype.loc['Weekday', 'delay_rate_pct']}% vs "
                     f"{dtype.loc['Weekend', 'delay_rate_pct']}%.")
    dd = tables["disruption_days"]
    if len(dd):
        top10_share = 100 * dd["cancelled"].sum() / max(int(df["cancelled"].sum()), 1)
        lines += [f"- **Event-driven disruption:** the {len(dd)} worst days alone hold {top10_share:.1f}% of all cancellations "
                  f"(worst: {pd.Timestamp(dd.iloc[0]['fl_date']).date()} with {dd.iloc[0]['cancel_rate_pct']}% cancelled).", "",
                  _fmt_table(dd.assign(fl_date=pd.to_datetime(dd["fl_date"]).dt.date),
                             {"fl_date": "Date", "flights": "Flights", "cancel_rate_pct": "Cancel rate %",
                              "delay_rate_pct": "Delay rate %"}, 5)]
    hc = tables["delay_causes_by_hour"].set_index("scheduled_dep_hour")
    if {6, 20} <= set(hc.index):
        lines += ["", f"- **Cascade evidence:** late-aircraft share of delay minutes rises from {hc.loc[6, 'Late Aircraft']}% for 06:00 "
                      f"departures to {hc.loc[20, 'Late Aircraft']}% for 20:00 departures."]
    reasons = tables["cancellation_reasons"]
    if len(reasons):
        r0 = reasons.iloc[0]
        lines += ["", "## 6. Why are flights cancelled?",
                  f"- Leading reason: **{r0['cancellation_reason']}** ({r0['share_pct']}% of cancellations)."]
    out = quality.get("outliers")
    if out:
        sev = tables["delay_severity"]
        lines += ["", "## 7. Outliers: small in number, large in impact",
                  f"- {out['extreme_delay_flights']:,} flights ({out['extreme_delay_pct_of_completed']}% of completed) were "
                  f">= {out['extreme_delay_threshold_min']} min late, yet account for "
                  f"**{out['extreme_delay_share_of_positive_delay_minutes_pct']}%** of all positive delay minutes.",
                  f"- Mean arrival delay is {out['mean_arr_delay_raw']} min raw vs {out['mean_arr_delay_winsorized']} min winsorized "
                  f"(median {out['median_arr_delay']}); {out['flights_over_24h_late']} flights were > 24 h late "
                  f"(max {out['max_arr_delay_min']:.0f} min).",
                  "- No rows were removed: extreme delays are real events; rankings use winsorized means.", "",
                  _fmt_table(sev, {"severity": "Severity", "flights": "Flights",
                                   "pct_of_delayed_flights": "% of delayed flights",
                                   "pct_of_delay_minutes": "% of delay minutes"}, 6)]
    lines += ["", "## 8. Data quality",
              f"- Rows: {quality['rows_clean']:,} | cancelled: {quality['cancelled_flights']:,} "
              f"| diverted: {quality['diverted_flights']:,}",
              "- Delay-cause minutes that do not sum to arrival delay: "
              f"{quality.get('delay_cause_sum_mismatch_pct', 'n/a')}%",
              "", "> Interpretation note: results describe association, not causation. "
              "See docs/business_problem.md for scope and limitations."]
    return "\n".join(lines)


def write_report(text: str, path: str | Path) -> None:
    """Persist the markdown report."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    log.info("Insight report written -> %s", path)
