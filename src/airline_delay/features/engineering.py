"""Business-driven feature engineering.

Every feature added here exists to answer one of the project's business
questions (see docs/business_problem.md). Features are derived with
vectorised operations only, so the step stays fast on millions of rows.
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from airline_delay.data.cleaning import completed_mask, minutes_to_hour
from airline_delay.data.schema import DELAY_CAUSE_COLUMNS
from airline_delay.features.outliers import add_outlier_features
from airline_delay.logging_utils import get_logger

log = get_logger(__name__)


def add_flight_status(df: pd.DataFrame) -> pd.DataFrame:
    """Create human-readable arrival / departure status labels.

    Priority: Cancelled > Diverted > (Early | On Time | Late) based on the sign of the delay.
    Using ``np.select`` guarantees every row gets exactly one label (the
    notebook initialised with 'Unknown' and overwrote it in several passes).
    """
    done = completed_mask(df)

    arr_conditions = [
        df["cancelled"] == 1,
        df["diverted"] == 1,
        done & (df["arr_delay"] < 0),
        done & (df["arr_delay"] == 0),
        done & (df["arr_delay"] > 0),
    ]
    dep_conditions = arr_conditions[:2] + [
        done & (df["dep_delay"] < 0),
        done & (df["dep_delay"] == 0),
        done & (df["dep_delay"] > 0),
    ]
    arr_labels = ["Cancelled", "Diverted", "Arrived Early", "Arrived On Time", "Arrived Late"]
    dep_labels = ["Cancelled", "Diverted", "Departed Early", "Departed On Time", "Departed Late"]

    df["arrival_status"] = np.select([c.fillna(False) for c in arr_conditions], arr_labels, default="Unknown")
    df["departure_status"] = np.select([c.fillna(False) for c in dep_conditions], dep_labels, default="Unknown")
    return df


def add_time_features(df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    """Calendar and time-of-day features used for seasonality / peak-hour analysis."""
    rules, look = cfg["business_rules"], cfg["lookups"]

    df["scheduled_dep_hour"] = minutes_to_hour(df["crs_dep_time"])
    df["actual_dep_hour"] = minutes_to_hour(df["dep_time"])
    df["is_weekend"] = df["day_of_week"].isin(rules["weekend_days"]).astype("int8")
    df["day_type"] = np.where(df["is_weekend"] == 1, "Weekend", "Weekday")
    df["month_name"] = df["month"].map(lambda m: look["month_names"][int(m) - 1])
    df["day_name"] = df["day_of_week"].map(look["day_names"])
    df["season"] = df["month"].map(look["seasons"])
    df["dep_daypart"] = pd.cut(
        df["scheduled_dep_hour"].astype("float"),
        bins=rules["daypart_bins"], labels=rules["daypart_labels"],
    ).astype("string")
    return df


def add_route_features(df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    """Route, airline-name, airport-label and haul-length features."""
    rules, look = cfg["business_rules"], cfg["lookups"]

    df["route"] = df["origin"] + " → " + df["dest"]
    df["airline_name"] = df["op_unique_carrier"].map(look["airline_names"]).fillna(df["op_unique_carrier"])
    # "Atlanta, Georgia" style label (city name in BTS is "Atlanta, GA" - we use the full state name)
    df["origin_label"] = df["origin"] + " (" + df["origin_city_name"].str.split(",").str[0] + ")"
    df["dest_label"] = df["dest"] + " (" + df["dest_city_name"].str.split(",").str[0] + ")"
    df["haul"] = pd.cut(
        df["distance"].astype("float"), bins=rules["haul_bins"], labels=rules["haul_labels"],
    ).astype("string")
    return df


def add_delay_features(df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    """KPI flags and diagnostic delay features.

    * ``is_arr_delayed``  - DOT on-time standard: arrival delay >= 15 min (completed flights only;
      ``<NA>`` for cancelled/diverted so they never silently count as 'on time').
    * ``is_dep_delayed``  - same rule on departure delay.
    * ``delay_recovered`` - minutes made up in the air = dep_delay - arr_delay
      (positive => the pilot recovered time; negative => lost more time en route).
    * ``primary_delay_cause`` - the largest of the five BTS cause columns for flights with >= threshold delay.
    """
    thr = cfg["business_rules"]["delay_threshold_minutes"]
    done = completed_mask(df)

    df["is_arr_delayed"] = pd.array(np.where(done, (df["arr_delay"] >= thr).astype("float"), np.nan), dtype="Int8")
    df["is_dep_delayed"] = pd.array(np.where(done, (df["dep_delay"] >= thr).astype("float"), np.nan), dtype="Int8")
    df["delay_recovered"] = (df["dep_delay"] - df["arr_delay"]).where(done)

    # Primary cause = column with the most minutes (ties resolved by column order)
    causes = df[DELAY_CAUSE_COLUMNS].fillna(0).astype(float)
    nice = {
        "carrier_delay": "Carrier", "weather_delay": "Weather", "nas_delay": "NAS",
        "security_delay": "Security", "late_aircraft_delay": "Late Aircraft",
    }
    primary = causes.idxmax(axis=1).map(nice)
    is_cause_flight = done & (df["arr_delay"] >= thr) & (causes.sum(axis=1) > 0)
    df["primary_delay_cause"] = primary.where(is_cause_flight).astype("string")
    return df


def add_cancellation_reason(df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    """Translate BTS cancellation codes (A/B/C/D) into readable reasons."""
    if "cancellation_code" in df.columns:
        df["cancellation_reason"] = df["cancellation_code"].map(cfg["lookups"]["cancellation_codes"]).astype("string")
    return df


def engineer_features(df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    """Apply every feature-engineering step in a fixed, documented order."""
    df = df.copy()
    df = add_flight_status(df)
    df = add_time_features(df, cfg)
    df = add_route_features(df, cfg)
    df = add_delay_features(df, cfg)
    df = add_cancellation_reason(df, cfg)
    df = add_outlier_features(df, cfg)  # flags + winsorized delays (no rows dropped)
    log.info("Feature engineering complete: %s columns", df.shape[1])
    return df
