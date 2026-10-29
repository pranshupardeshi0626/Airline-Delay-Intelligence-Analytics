"""KPI / aggregation layer.

All functions are *pure*: they take a DataFrame and return a DataFrame/dict and
never plot or write files. That makes every business number reproducible,
unit-testable and reusable from notebooks, the CLI or a future dashboard.

KPI definitions (aligned with US DOT Air Travel Consumer Report)
----------------------------------------------------------------
* cancel_rate_pct   = cancelled flights / all scheduled flights x 100
* diverted_rate_pct = diverted flights  / all scheduled flights x 100
* delay_rate_pct    = completed flights arriving >= 15 min late / completed flights x 100
* ontime_pct        = 100 - delay_rate_pct   (of *completed* flights)
* avg_*_delay       = mean delay in minutes (negative values = early arrival are included)
* p90_arr_delay     = 90th percentile of arrival delay (captures the "bad day" experience
                      that averages hide)
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd

from airline_delay.data.cleaning import completed_mask
from airline_delay.data.schema import DELAY_CAUSE_COLUMNS

CAUSE_LABELS = {
    "carrier_delay": "Carrier",
    "weather_delay": "Weather",
    "nas_delay": "NAS",
    "security_delay": "Security",
    "late_aircraft_delay": "Late Aircraft",
}


def _as_list(by: str | Iterable[str]) -> List[str]:
    """Normalise a column name or iterable of names to a list."""
    return [by] if isinstance(by, str) else list(by)


def network_kpis(df: pd.DataFrame, cfg: Dict[str, Any]) -> Dict[str, float]:
    """Headline KPIs for the whole network (used on the executive summary)."""
    done = completed_mask(df)
    thr = cfg["business_rules"]["delay_threshold_minutes"]
    arr = df.loc[done, "arr_delay"].astype(float)
    late = arr >= thr
    delayed_minutes = arr[late].sum()
    return {
        "total_flights": int(len(df)),
        "completed_flights": int(done.sum()),
        "cancel_rate_pct": round(100 * float(df["cancelled"].mean()), 2),
        "diverted_rate_pct": round(100 * float(df["diverted"].mean()), 2),
        "delay_rate_pct": round(100 * float(late.mean()), 2),
        "ontime_pct": round(100 * float(1 - late.mean()), 2),
        "avg_dep_delay_min": round(float(df["dep_delay"].astype(float).mean()), 2),
        "avg_arr_delay_min": round(float(arr.mean()), 2),
        "avg_arr_delay_winsorized_min": round(float(df.loc[done, "arr_delay_w"].mean()), 2),
        "median_arr_delay_min": round(float(arr.median()), 2),
        "p90_arr_delay_min": round(float(arr.quantile(0.9)), 2),
        "avg_delay_when_delayed_min": round(float(arr[late].mean()), 2),
        "total_delay_hours": round(float(delayed_minutes) / 60, 0),
    }


def carryover_kpis(df: pd.DataFrame, cfg: Dict[str, Any]) -> Dict[str, float]:
    """How a departure delay turns into an arrival delay (completed flights).

    * dep_late_arr_late_pct   - of flights leaving >= threshold late, % that also arrive >= threshold late
    * dep_ok_arr_late_pct     - of flights leaving on time, % that still arrive late (en-route / NAS problems)
    * arr_late_left_on_time_pct - of late arrivals, % that departed on time
    * avg_minutes_recovered   - mean minutes made up in the air by flights that left >= threshold late
    """
    thr = cfg["business_rules"]["delay_threshold_minutes"]
    c = df[completed_mask(df)]
    dep, arr = c["dep_delay"].astype(float), c["arr_delay"].astype(float)
    return {
        "dep_late_arr_late_pct": round(100 * float((arr[dep >= thr] >= thr).mean()), 1),
        "dep_ok_arr_late_pct": round(100 * float((arr[dep < thr] >= thr).mean()), 1),
        "arr_late_left_on_time_pct": round(100 * float((dep[arr >= thr] < thr).mean()), 1),
        "avg_minutes_recovered": round(float(c.loc[dep >= thr, "delay_recovered"].astype(float).mean()), 1),
    }


def disruption_days(daily: pd.DataFrame, n: int = 10, min_flights: int = 1000) -> pd.DataFrame:
    """Calendar days with the highest cancellation rate (event-driven disruption: storms, IT outages ...)."""
    return daily[daily["flights"] >= min_flights].sort_values("cancel_rate_pct", ascending=False).head(n).reset_index(drop=True)


def group_kpis(df: pd.DataFrame, by: str | Iterable[str], cfg: Dict[str, Any],
               min_flights: int = 0) -> pd.DataFrame:
    """Reliability KPIs for any grouping (airline, airport, route, hour, month ...).

    Parameters
    ----------
    by:
        Column or list of columns to group on.
    min_flights:
        Groups with fewer scheduled flights are dropped. Small groups produce
        extreme averages (e.g. 2 flights, one 6-hour delay) that would otherwise
        dominate every "worst performer" ranking.
    """
    by = _as_list(by)
    work = df[by + ["cancelled", "diverted", "dep_delay", "arr_delay", "dep_delay_w", "arr_delay_w",
                    "is_arr_delayed", "is_extreme_delay"]].copy()
    # Convert nullable Int -> float so groupby aggregations skip NaN correctly
    for c in ("dep_delay", "arr_delay", "dep_delay_w", "arr_delay_w", "is_arr_delayed"):
        work[c] = work[c].astype(float)
    # IMPORTANT: the flags are stored as int8 to save memory; summing int8 per group
    # silently overflows (>127) and produced negative cancel rates. Widen before aggregating.
    for c in ("cancelled", "diverted"):
        work[c] = work[c].astype("int64")

    g = work.groupby(by, observed=True, dropna=True)
    out = g.agg(
        flights=("cancelled", "size"),
        cancelled=("cancelled", "sum"),
        diverted=("diverted", "sum"),
        delayed=("is_arr_delayed", "sum"),
        completed=("is_arr_delayed", "count"),
        avg_dep_delay=("dep_delay", "mean"),
        avg_arr_delay=("arr_delay", "mean"),
        # winsorized means (robust to a few multi-day delays) - used for RANKINGS
        avg_dep_delay_w=("dep_delay_w", "mean"),
        avg_arr_delay_w=("arr_delay_w", "mean"),
        median_arr_delay=("arr_delay", "median"),
        extreme_delays=("is_extreme_delay", "sum"),
    )
    out["p90_arr_delay"] = g["arr_delay"].quantile(0.9)
    out["cancel_rate_pct"] = 100 * out["cancelled"] / out["flights"]
    out["diverted_rate_pct"] = 100 * out["diverted"] / out["flights"]
    out["delay_rate_pct"] = 100 * out["delayed"] / out["completed"].replace(0, np.nan)
    out["ontime_pct"] = 100 - out["delay_rate_pct"]
    out = out[out["flights"] >= min_flights].reset_index()
    num = out.select_dtypes("number").columns  # don't round datetime group keys (e.g. fl_date)
    out[num] = out[num].round(2)
    return out


def delay_severity(df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    """How delay *minutes* concentrate in the long tail.

    For delayed flights (>= threshold) bucket by severity and show each bucket's share of
    flights vs share of delay minutes. A tiny share of flights carrying a large share of
    minutes is the quantitative case for treating extreme delays separately.
    """
    o = cfg["outliers"]
    done = completed_mask(df)
    d = df.loc[done & (df["arr_delay"] >= o["severity_bins"][0]), "arr_delay"].astype(float)
    bucket = pd.cut(d, bins=o["severity_bins"], labels=o["severity_labels"], right=False)
    g = d.groupby(bucket, observed=True).agg(flights="size", delay_minutes="sum").reset_index(names="severity")
    g["pct_of_delayed_flights"] = 100 * g["flights"] / g["flights"].sum()
    g["pct_of_delay_minutes"] = 100 * g["delay_minutes"] / g["delay_minutes"].sum()
    return g.round(2)


def delay_cause_summary(df: pd.DataFrame, cfg: Dict[str, Any],
                        by: str | Iterable[str] | None = None) -> pd.DataFrame:
    """Average delay minutes and % share per cause, among *delayed* flights only.

    BTS only records cause minutes for flights arriving >= 15 min late, and the
    remaining flights carry zeros. Averaging over all flights (as the original
    notebook did) therefore dilutes every cause by the ~80 % of on-time flights
    and makes causes look much smaller than they are when a delay actually happens.
    """
    thr = cfg["business_rules"]["delay_threshold_minutes"]
    delayed = df[completed_mask(df) & (df["arr_delay"] >= thr)].copy()
    cols = DELAY_CAUSE_COLUMNS
    delayed[cols] = delayed[cols].astype(float)

    if by is None:
        tot = delayed[cols].sum()
        res = pd.DataFrame({
            "cause": [CAUSE_LABELS[c] for c in cols],
            "total_minutes": tot.values,
            "avg_minutes_per_delayed_flight": delayed[cols].mean().values,
        })
        res["share_pct"] = 100 * res["total_minutes"] / res["total_minutes"].sum()
        return res.round(2)

    by = _as_list(by)
    grp = delayed.groupby(by, observed=True)[cols].sum()
    share = grp.div(grp.sum(axis=1).replace(0, np.nan), axis=0) * 100
    share.columns = [CAUSE_LABELS[c] for c in cols]
    share["delayed_flights"] = delayed.groupby(by, observed=True).size()
    return share.reset_index().round(2)


def cancellation_reasons(df: pd.DataFrame) -> pd.DataFrame:
    """Count and share of cancellations by BTS reason code."""
    if "cancellation_reason" not in df.columns:
        return pd.DataFrame(columns=["cancellation_reason", "flights", "share_pct"])
    c = df.loc[df["cancelled"] == 1, "cancellation_reason"].fillna("Unknown").value_counts()
    res = c.rename_axis("cancellation_reason").reset_index(name="flights")
    res["share_pct"] = (100 * res["flights"] / res["flights"].sum()).round(2)
    return res


def pivot_metric(df: pd.DataFrame, index: str, columns: str, value: str, agg: str = "mean",
                 scale: float = 1.0) -> pd.DataFrame:
    """Pivot table helper for heatmaps (e.g. month x hour average delay)."""
    work = df[[index, columns, value]].copy()
    work[value] = work[value].astype(float)
    return work.pivot_table(index=index, columns=columns, values=value, aggfunc=agg, observed=True) * scale


def correlation_matrix(df: pd.DataFrame, cols: List[str] | None = None) -> pd.DataFrame:
    """Pearson correlation between delay drivers, using completed flights only."""
    cols = cols or ["dep_delay", "arr_delay", *DELAY_CAUSE_COLUMNS, "taxi_out", "taxi_in", "air_time", "distance"]
    return df.loc[completed_mask(df), cols].astype(float).corr().round(3)


def rank_worst(table: pd.DataFrame, metric: str, n: int = 15) -> pd.DataFrame:
    """Top-n rows by metric (descending)."""
    return table.sort_values(metric, ascending=False).head(n).reset_index(drop=True)
