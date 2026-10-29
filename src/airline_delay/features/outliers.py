"""Outlier detection and robust-statistics support.

Policy (decided after profiling the real data)
----------------------------------------------
Airline delay is **heavy-tailed**: the median arrival is ~6 min *early* while a handful of
flights are 20-56 hours late (overnight cancellations re-flown the next day, aircraft swaps ...).
Those flights are real operational events, not errors, so this module **never drops rows**.
Instead it:

1. flags extreme delays (``is_extreme_delay``) so their weight can be measured and shown;
2. creates winsorized delay columns (``dep_delay_w`` / ``arr_delay_w``) used for *rankings*, so a single
   3,000-minute flight cannot decide which airport or route is "worst";
3. flags physically implausible / inconsistent records for data-quality review (never silently fixed).
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from airline_delay.data.cleaning import completed_mask

MINUTES_PER_DAY = 1440


def _winsor_caps(df: pd.DataFrame, cfg: Dict[str, Any]) -> Dict[str, float]:
    """Winsorization caps from the data itself (completed flights only)."""
    o = cfg["outliers"]
    done = completed_mask(df)
    caps = {}
    for col in ("dep_delay", "arr_delay"):
        v = df.loc[done, col].astype(float).dropna()
        caps[col] = (float(np.percentile(v, o["winsor_lower_pct"])), float(np.percentile(v, o["winsor_upper_pct"])))
    return caps


def add_outlier_features(df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    """Add outlier flags and winsorized delay columns (no rows are removed)."""
    o = cfg["outliers"]
    done = completed_mask(df)

    arr = df["arr_delay"].astype(float)
    dep = df["dep_delay"].astype(float)

    # --- 1. Extreme delay (real but rare, very costly)
    df["is_extreme_delay"] = (done & (arr >= o["extreme_delay_minutes"])).astype("int8")

    # --- 2. Winsorized delays for robust averages / rankings
    caps = _winsor_caps(df, cfg)
    df["arr_delay_w"] = arr.clip(*caps["arr_delay"])
    df["dep_delay_w"] = dep.clip(*caps["dep_delay"])

    # --- 3. Physical / consistency flags (data quality, not business outliers)
    air_hours = df["air_time"].astype(float) / 60
    speed = (df["distance"].astype(float) / air_hours.where(air_hours > 0)).where(done)
    lo, hi = o["speed_mph_bounds"]
    df["is_speed_anomaly"] = ((speed < lo) | (speed > hi)).fillna(False).astype("int8")
    df["is_taxi_anomaly"] = (
        (df["taxi_out"].astype(float) > o["taxi_out_max"]) | (df["taxi_in"].astype(float) > o["taxi_in_max"])
    ).fillna(False).astype("int8")

    # Actual clock time must equal scheduled time + reported delay (mod 24 h)
    dep_gap = (df["dep_time"].astype(float) - df["crs_dep_time"].astype(float) - dep) % MINUTES_PER_DAY
    arr_gap = (df["arr_time"].astype(float) - df["crs_arr_time"].astype(float) - arr) % MINUTES_PER_DAY
    df["is_time_inconsistent"] = (done & ((dep_gap != 0) | (arr_gap != 0))).fillna(False).astype("int8")
    return df


def summarize_outliers(df: pd.DataFrame, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Quantify how much the outliers matter (goes into the quality report and the findings)."""
    done = completed_mask(df)
    arr = df.loc[done, "arr_delay"].astype(float)
    pos = arr[arr > 0]
    ext = df.loc[done, "is_extreme_delay"] == 1
    caps = _winsor_caps(df, cfg)
    return {
        "extreme_delay_threshold_min": cfg["outliers"]["extreme_delay_minutes"],
        "extreme_delay_flights": int(ext.sum()),
        "extreme_delay_pct_of_completed": round(100 * float(ext.mean()), 3),
        "extreme_delay_share_of_positive_delay_minutes_pct": round(100 * float(arr[ext].sum() / pos.sum()), 2),
        "flights_over_24h_late": int((arr >= 1440).sum()),
        "max_arr_delay_min": float(arr.max()),
        "mean_arr_delay_raw": round(float(arr.mean()), 2),
        "mean_arr_delay_winsorized": round(float(df.loc[done, "arr_delay_w"].mean()), 2),
        "median_arr_delay": float(arr.median()),
        "winsor_caps_arr_delay": [round(c, 1) for c in caps["arr_delay"]],
        "speed_anomalies": int(df["is_speed_anomaly"].sum()),
        "taxi_anomalies": int(df["is_taxi_anomaly"].sum()),
        "time_inconsistent_records": int(df["is_time_inconsistent"].sum()),
    }
