"""Data access for the dashboard: cached loading, filtering and aggregation.

Performance design (1M rows must stay interactive)
--------------------------------------------------
* The full dataset is loaded ONCE with ``st.cache_resource`` (no per-rerun copying) and downcast
  (float32 numbers, categorical strings) to cut memory.
* A filter selection is a small *hashable* ``Filters`` tuple. The filtered frame is cached per
  selection (``max_entries`` keeps memory bounded) and every aggregate is cached by that same key,
  so moving between pages is instant and only a filter change recomputes anything.
* All KPI maths is delegated to ``airline_delay.analysis.metrics`` - the dashboard and the batch
  pipeline therefore always agree.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from airline_delay.analysis import metrics as M  # noqa: E402
from airline_delay.config import load_config, resolve_path  # noqa: E402

CFG = load_config()
RULES = CFG["business_rules"]
DAY_NAMES = [CFG["lookups"]["day_names"][i] for i in range(1, 8)]
MONTH_NAMES = CFG["lookups"]["month_names"]

NEEDED_COLUMNS = [
    "fl_date", "month", "day_of_week", "day_name", "day_type", "scheduled_dep_hour", "dep_daypart", "haul", "season",
    "op_unique_carrier", "airline_name", "origin", "origin_label", "origin_state_nm", "dest", "dest_label", "route",
    "cancelled", "diverted", "cancellation_reason", "dep_delay", "arr_delay", "dep_delay_w", "arr_delay_w",
    "is_arr_delayed", "is_extreme_delay", "delay_recovered", "arrival_status", "primary_delay_cause",
    "carrier_delay", "weather_delay", "nas_delay", "security_delay", "late_aircraft_delay",
    "taxi_out", "taxi_in", "air_time", "distance",
]
CATEGORICAL = ["day_name", "day_type", "dep_daypart", "haul", "season", "op_unique_carrier", "airline_name", "origin",
               "origin_label", "origin_state_nm", "dest", "dest_label", "route", "cancellation_reason",
               "arrival_status", "primary_delay_cause"]


def data_path() -> Path:
    """Processed dataset path (override with the AIRLINE_DASHBOARD_DATA environment variable)."""
    env = os.environ.get("AIRLINE_DASHBOARD_DATA")
    return Path(env) if env else resolve_path(CFG["paths"]["processed_data"])


@st.cache_resource(show_spinner="Loading flight data ...")
def load_data() -> pd.DataFrame | None:
    """Load + downcast the analysis-ready dataset. Returns None when the pipeline has not been run."""
    p = data_path()
    if not p.exists():
        return None
    df = pd.read_parquet(p, columns=[c for c in NEEDED_COLUMNS])
    for c in df.columns:
        if c in CATEGORICAL:
            df[c] = df[c].astype("category")
        elif c not in ("fl_date",) and str(df[c].dtype) in ("Int64", "Int8", "Int32", "Float64"):
            df[c] = df[c].astype("float32")  # nullable ints -> NaN floats (fast, half the memory)
    for c in ("cancelled", "diverted", "is_extreme_delay"):
        df[c] = df[c].astype("int8")
    return df


# --------------------------------------------------------------------------- filters
@dataclass(frozen=True)
class Filters:
    """Hashable filter selection (used as cache key)."""
    airlines: Tuple[str, ...] = ()
    months: Tuple[int, int] = (1, 12)
    days: Tuple[str, ...] = ()
    dayparts: Tuple[str, ...] = ()
    hauls: Tuple[str, ...] = ()
    origins: Tuple[str, ...] = ()
    drop_extreme: bool = False
    winsor: bool = True


@st.cache_resource(max_entries=4, show_spinner="Applying filters ...")
def get_filtered(f: Filters) -> pd.DataFrame:
    """Rows matching the filter selection (empty selection = no restriction)."""
    df = load_data()
    mask = df["month"].between(f.months[0], f.months[1])
    if f.airlines:
        mask &= df["airline_name"].isin(f.airlines)
    if f.days:
        mask &= df["day_name"].isin(f.days)
    if f.dayparts:
        mask &= df["dep_daypart"].isin(f.dayparts)
    if f.hauls:
        mask &= df["haul"].isin(f.hauls)
    if f.origins:
        mask &= df["origin_label"].isin(f.origins)
    if f.drop_extreme:
        mask &= df["is_extreme_delay"] == 0
    return df[mask]


def dcols(f: Filters) -> Tuple[str, str]:
    """Names of the (departure, arrival) average-delay columns honouring the winsorization toggle."""
    return ("avg_dep_delay_w", "avg_arr_delay_w") if f.winsor else ("avg_dep_delay", "avg_arr_delay")


# --------------------------------------------------------------------------- cached aggregates
@st.cache_data(show_spinner=False, max_entries=64)
def kpis(f: Filters) -> dict:
    """Headline KPIs + carry-over KPIs for the selection."""
    df = get_filtered(f)
    if len(df) == 0:
        return {}
    return {**M.network_kpis(df, CFG), **M.carryover_kpis(df, CFG), "extreme": int(df["is_extreme_delay"].sum())}


@st.cache_data(show_spinner=False)
def baseline_kpis() -> dict:
    """KPIs of the whole network (used for 'vs network' deltas)."""
    df = load_data()
    return {**M.network_kpis(df, CFG), **M.carryover_kpis(df, CFG), "extreme": int(df["is_extreme_delay"].sum())}


@st.cache_data(show_spinner=False, max_entries=128)
def group(f: Filters, by: Tuple[str, ...], min_flights: int = 0) -> pd.DataFrame:
    """Generic grouped reliability KPIs (airline, airport, route, hour, month, day ...)."""
    df = get_filtered(f)
    if len(df) == 0:
        return pd.DataFrame()
    g = M.group_kpis(df, list(by), CFG, min_flights)
    g["extreme_rate_pct"] = (100 * g["extreme_delays"] / g["completed"].replace(0, np.nan)).round(2)
    return g


@st.cache_data(show_spinner=False, max_entries=64)
def causes(f: Filters, by: str | None = None) -> pd.DataFrame:
    """Delay-cause mix (network or per group)."""
    df = get_filtered(f)
    return M.delay_cause_summary(df, CFG, by=by) if len(df) else pd.DataFrame()


@st.cache_data(show_spinner=False)
def severity(f: Filters) -> pd.DataFrame:
    """Delay-severity buckets (outlier impact)."""
    df = get_filtered(f)
    return M.delay_severity(df, CFG) if len(df) else pd.DataFrame()


@st.cache_data(show_spinner=False)
def cancel_reasons(f: Filters) -> pd.DataFrame:
    """Cancellation reasons."""
    df = get_filtered(f)
    return M.cancellation_reasons(df) if len(df) else pd.DataFrame()


@st.cache_data(show_spinner=False, max_entries=32)
def pivot(f: Filters, index: str, columns: str, value: str, scale: float = 1.0) -> pd.DataFrame:
    """Two-way pivot of a metric (heatmaps)."""
    df = get_filtered(f)
    if len(df) == 0:
        return pd.DataFrame()
    return M.pivot_metric(df, index, columns, value, scale=scale)


@st.cache_data(show_spinner=False)
def correlations(f: Filters) -> pd.DataFrame:
    """Correlation of delay drivers."""
    df = get_filtered(f)
    return M.correlation_matrix(df) if len(df) else pd.DataFrame()


@st.cache_data(show_spinner=False)
def sample(f: Filters, n: int = 20000) -> pd.DataFrame:
    """Reproducible random sample of completed flights for scatter plots."""
    df = get_filtered(f)
    done = df[(df["cancelled"] == 0) & (df["diverted"] == 0)]
    return done.sample(min(n, len(done)), random_state=42)[["dep_delay", "arr_delay", "airline_name", "haul"]]


@st.cache_data(show_spinner=False)
def histogram(f: Filters, col: str, lo: int = -60, hi: int = 240, step: int = 5) -> pd.DataFrame:
    """Pre-binned histogram counts for completed flights (clipped to [lo, hi])."""
    df = get_filtered(f)
    done = df[(df["cancelled"] == 0) & (df["diverted"] == 0)][col].astype(float).dropna().clip(lo, hi)
    edges = np.arange(lo, hi + step, step)
    counts, _ = np.histogram(done, bins=edges)
    return pd.DataFrame({"minutes": edges[:-1] + step / 2, "flights": counts})


@st.cache_data(show_spinner=False)
def day_detail(f: Filters, date: str) -> dict:
    """Everything needed to drill into one calendar day."""
    df = get_filtered(f)
    d = df[df["fl_date"] == pd.Timestamp(date)]
    if len(d) == 0:
        return {}
    return {
        "kpis": M.network_kpis(d, CFG),
        "airlines": M.group_kpis(d, "airline_name", CFG, 20).sort_values("cancel_rate_pct", ascending=False),
        "hours": M.group_kpis(d, "scheduled_dep_hour", CFG),
        "reasons": M.cancellation_reasons(d),
        "origins": M.group_kpis(d, "origin_label", CFG, 30).sort_values("cancel_rate_pct", ascending=False).head(8),
    }


@st.cache_data(show_spinner=False)
def route_detail(f: Filters, origin: str, dest: str) -> dict:
    """KPIs and breakdowns for a single origin -> destination pair."""
    df = get_filtered(f)
    d = df[(df["origin"] == origin) & (df["dest"] == dest)]
    if len(d) == 0:
        return {}
    return {
        "kpis": M.network_kpis(d, CFG),
        "airlines": M.group_kpis(d, "airline_name", CFG),
        "hours": M.group_kpis(d, "scheduled_dep_hour", CFG),
        "months": M.group_kpis(d, "month", CFG),
        "flights": len(d),
    }


@st.cache_data(show_spinner=False)
def dest_options(f: Filters, origin: str) -> list[str]:
    """Destinations flown from an origin (by IATA code), most frequent first."""
    df = get_filtered(f)
    return df.loc[df["origin"] == origin, "dest"].value_counts().loc[lambda s: s > 0].index.astype(str).tolist()


@st.cache_data(show_spinner=False)
def airport_names() -> dict:
    """IATA code -> 'CODE (City)' label for dropdowns (deduplicated first: 1M rows -> ~350 pairs)."""
    df = load_data()
    out: dict = {}
    for code, label in (("dest", "dest_label"), ("origin", "origin_label")):
        pairs = df[[code, label]].drop_duplicates()
        out.update(dict(zip(pairs[code].astype(str), pairs[label].astype(str), strict=False)))
    return out
