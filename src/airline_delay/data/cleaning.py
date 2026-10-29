"""Data cleaning: raw BTS flight records -> typed, consistent, analysis-ready table.

Design decisions (and fixes versus the original exploratory notebook)
--------------------------------------------------------------------
* Clock times (HHMM floats such as ``1435.0``) are converted to **minutes since
  midnight** (``Int64``) instead of fake ``1900-01-01`` datetimes. This avoids a
  meaningless date component and makes arithmetic (``dep + delay``) trivial.
  The BTS value ``2400`` (midnight) is normalised to ``0``.
* Missing *actual* times of **completed** flights are rebuilt from their
  components (dep_time = scheduled + delay, wheels_off = dep + taxi_out, ...),
  using modulo-1440 arithmetic so times that cross midnight stay valid.
  Cancelled / diverted flights are never imputed: their blanks are real
  information (the flight did not complete), not data errors.
* ``cancellation_code`` is **kept**. It is empty for non-cancelled flights by
  design (the original notebook dropped it because it was >40 % null, losing the
  cancellation *reason*).
* ``op_carrier_fl_num`` is converted ``float -> Int64 -> str`` so flight numbers
  don't end up as ``"1234.0"``.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

from airline_delay.data.schema import DELAY_CAUSE_COLUMNS, HHMM_COLUMNS, MINUTE_COLUMNS
from airline_delay.logging_utils import get_logger

log = get_logger(__name__)

MINUTES_PER_DAY = 1440


# --------------------------------------------------------------------------- #
# Low-level helpers
# --------------------------------------------------------------------------- #
def hhmm_to_minutes(series: pd.Series) -> pd.Series:
    """Convert HHMM-encoded clock values (e.g. 1435) to minutes since midnight.

    Invalid values (minutes >= 60, hours > 24, negatives, NaN) become ``<NA>``.
    ``2400`` is treated as ``0000`` of the same day.
    """
    s = pd.to_numeric(series, errors="coerce")
    hours = np.floor(s / 100)
    mins = s - hours * 100
    valid = s.notna() & (s >= 0) & (s <= 2400) & (mins < 60)
    total = (hours * 60 + mins).where(valid)
    # 24:00 == 00:00 (next-day midnight in BTS notation)
    total = total % MINUTES_PER_DAY
    return total.round().astype("Int64")


def minutes_to_hour(series: pd.Series) -> pd.Series:
    """Hour-of-day (0-23) from minutes since midnight, preserving ``<NA>``."""
    return (series // 60).astype("Int64")


# --------------------------------------------------------------------------- #
# Cleaning steps (each is small, pure and individually testable)
# --------------------------------------------------------------------------- #
def convert_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Cast every column to its proper analytical type."""
    df = df.copy()

    # Flight date -> datetime64
    df["fl_date"] = pd.to_datetime(df["fl_date"], errors="coerce")

    # HHMM clock columns -> minutes since midnight
    for col in HHMM_COLUMNS:
        df[col] = hhmm_to_minutes(df[col])

    # Minute-valued columns -> nullable integers (keeps NA for cancelled flights)
    for col in MINUTE_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").round().astype("Int64")

    df["distance"] = pd.to_numeric(df["distance"], errors="coerce").astype("Int64")

    # Flags -> small ints
    for col in ("cancelled", "diverted"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int8")

    # Flight number: float -> Int64 -> str (avoids "1234.0")
    df["op_carrier_fl_num"] = (
        pd.to_numeric(df["op_carrier_fl_num"], errors="coerce").astype("Int64").astype("string")
    )

    # Categorical-like text columns: trim whitespace and standardise case for codes
    for col in ("op_unique_carrier", "origin", "dest"):
        df[col] = df[col].astype("string").str.strip().str.upper()
    if "cancellation_code" in df.columns:
        df["cancellation_code"] = df["cancellation_code"].astype("string").str.strip().str.upper()

    return df


def drop_constant_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop columns that hold a single value (zero information, e.g. ``year``)."""
    constant = [c for c in df.columns if df[c].nunique(dropna=False) <= 1]
    if constant:
        log.info("Dropping constant columns: %s", constant)
    return df.drop(columns=constant)


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Remove exact duplicate rows and log how many were found."""
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    log.info("Duplicate rows removed: %s", f"{before - len(df):,}")
    return df


def completed_mask(df: pd.DataFrame) -> pd.Series:
    """Boolean mask of flights that took off *and* landed at the planned destination."""
    return (df["cancelled"] == 0) & (df["diverted"] == 0)


def impute_completed_flight_times(df: pd.DataFrame) -> pd.DataFrame:
    """Rebuild missing actual clock times for completed flights from components.

    Chain of dependencies (each only fills blanks, never overwrites real data)::

        dep_time   = crs_dep_time + dep_delay
        wheels_off = dep_time     + taxi_out
        wheels_on  = wheels_off   + air_time
        arr_time   = wheels_on    + taxi_in

    Modulo 1440 keeps values valid when a flight crosses midnight.
    Cancelled and diverted flights are intentionally left untouched.
    """
    df = df.copy()
    ok = completed_mask(df)

    steps = [
        ("dep_time", "crs_dep_time", "dep_delay"),
        ("wheels_off", "dep_time", "taxi_out"),
        ("wheels_on", "wheels_off", "air_time"),
        ("arr_time", "wheels_on", "taxi_in"),
    ]
    for target, base, offset in steps:
        fill_rows = ok & df[target].isna() & df[base].notna() & df[offset].notna()
        n = int(fill_rows.sum())
        if n:
            df.loc[fill_rows, target] = (df.loc[fill_rows, base] + df.loc[fill_rows, offset]) % MINUTES_PER_DAY
            log.info("Imputed %s missing '%s' values for completed flights", f"{n:,}", target)
    return df


# --------------------------------------------------------------------------- #
# Data-quality report
# --------------------------------------------------------------------------- #
def build_quality_report(raw: pd.DataFrame, clean: pd.DataFrame, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Summarise the health of the cleaned data in a JSON-serialisable dict.

    Checks performed
    ----------------
    * row counts before/after cleaning
    * residual null counts for completed flights (should be ~0 for core metrics)
    * values outside configured plausibility bounds
    * contradictory flags (a flight both cancelled and diverted)
    * consistency of delay-cause minutes vs. arrival delay (BTS: causes should sum to
      ``arr_delay`` for flights delayed >= 15 minutes)
    """
    done = completed_mask(clean)
    report: Dict[str, Any] = {
        "rows_raw": int(len(raw)),
        "rows_clean": int(len(clean)),
        "completed_flights": int(done.sum()),
        "cancelled_flights": int((clean["cancelled"] == 1).sum()),
        "diverted_flights": int((clean["diverted"] == 1).sum()),
    }

    # Residual nulls among completed flights, core columns only
    core = ["dep_time", "dep_delay", "arr_time", "arr_delay", "taxi_out", "taxi_in", "air_time"]
    report["completed_flights_nulls"] = {c: int(clean.loc[done, c].isna().sum()) for c in core if c in clean}

    # Plausibility bounds
    bounds_violations = {}
    for col, (lo, hi) in cfg["cleaning"]["bounds"].items():
        if col in clean:
            vals = clean[col].dropna()
            bounds_violations[col] = int(((vals < lo) | (vals > hi)).sum())
    report["out_of_bounds"] = bounds_violations

    # Contradictory flags
    report["cancelled_and_diverted"] = int(((clean["cancelled"] == 1) & (clean["diverted"] == 1)).sum())

    # Delay-cause consistency (only meaningful for flights delayed >= threshold)
    thr = cfg["business_rules"]["delay_threshold_minutes"]
    delayed = done & (clean["arr_delay"] >= thr)
    if delayed.any():
        cause_sum = clean.loc[delayed, DELAY_CAUSE_COLUMNS].fillna(0).sum(axis=1)
        mismatch = (cause_sum != clean.loc[delayed, "arr_delay"]).sum()
        report["delay_cause_sum_mismatch_pct"] = round(100 * float(mismatch) / int(delayed.sum()), 3)
    return report


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
def clean_flights(raw: pd.DataFrame, cfg: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Run the full cleaning pipeline.

    Returns
    -------
    (clean_df, quality_report)
    """
    cl_cfg = cfg["cleaning"]
    df = convert_dtypes(raw)
    if cl_cfg.get("drop_constant_columns", True):
        df = drop_constant_columns(df)
    if cl_cfg.get("drop_duplicates", True):
        df = remove_duplicates(df)
    if cl_cfg.get("impute_timestamps_for_completed_flights", True):
        df = impute_completed_flight_times(df)

    report = build_quality_report(raw, df, cfg)
    log.info("Cleaning complete: %s rows retained", f"{len(df):,}")
    return df, report
