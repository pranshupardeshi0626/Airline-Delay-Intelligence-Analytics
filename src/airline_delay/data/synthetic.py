"""Synthetic data generator that mimics the BTS 2024 on-time schema.

PURPOSE: smoke-testing the pipeline, unit tests and CI when the 1M-row Kaggle
file is not available. The numbers it produces are **simulated and must never be
quoted as real airline performance**. Realistic structure is built in on purpose
(evening delay build-up, winter cancellations, late-aircraft-heavy cause mix,
causes summing to arrival delay) so that the pipeline logic is genuinely exercised.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CARRIERS = {"WN": 0.20, "DL": 0.14, "AA": 0.14, "UA": 0.11, "OO": 0.10, "YX": 0.04, "MQ": 0.04,
            "NK": 0.04, "AS": 0.035, "B6": 0.035, "OH": 0.03, "F9": 0.03, "9E": 0.03, "G4": 0.015, "HA": 0.01}
# Relative "delay proneness" per carrier (multiplier on delay scale)
CARRIER_FACTOR = {"WN": 1.0, "DL": 0.8, "AA": 1.1, "UA": 1.1, "OO": 0.9, "YX": 1.0, "MQ": 1.2, "NK": 1.3,
                  "AS": 0.85, "B6": 1.4, "OH": 1.0, "F9": 1.3, "9E": 1.1, "G4": 1.25, "HA": 0.6}
AIRPORTS = {  # code: (city, state, weight)
    "ATL": ("Atlanta, GA", "Georgia", 9), "DFW": ("Dallas/Fort Worth, TX", "Texas", 8),
    "DEN": ("Denver, CO", "Colorado", 8), "ORD": ("Chicago, IL", "Illinois", 7),
    "CLT": ("Charlotte, NC", "North Carolina", 5), "PHX": ("Phoenix, AZ", "Arizona", 5),
    "LAX": ("Los Angeles, CA", "California", 5), "LAS": ("Las Vegas, NV", "Nevada", 5),
    "SEA": ("Seattle, WA", "Washington", 4), "LGA": ("New York, NY", "New York", 4),
    "MCO": ("Orlando, FL", "Florida", 4), "BOS": ("Boston, MA", "Massachusetts", 4),
    "DCA": ("Washington, DC", "Virginia", 3), "SFO": ("San Francisco, CA", "California", 3),
    "DTW": ("Detroit, MI", "Michigan", 3), "EWR": ("Newark, NJ", "New Jersey", 3),
    "MSP": ("Minneapolis, MN", "Minnesota", 3), "JFK": ("New York, NY", "New York", 3),
    "IAH": ("Houston, TX", "Texas", 3), "SLC": ("Salt Lake City, UT", "Utah", 3),
    "HNL": ("Honolulu, HI", "Hawaii", 1), "ANC": ("Anchorage, AK", "Alaska", 1),
}
HOUR_WEIGHTS = np.array([2, 1, 1, 1, 1, 28, 70, 70, 68, 56, 62, 62, 59, 60, 58, 57, 58, 62, 61, 55, 45, 33, 24, 8], float)


def _to_hhmm(minutes: np.ndarray) -> np.ndarray:
    """Minutes since midnight -> HHMM float (NaN preserved)."""
    m = np.mod(minutes, 1440)
    return (m // 60) * 100 + (m % 60)


def generate_sample(n: int = 50_000, seed: int = 42) -> pd.DataFrame:
    """Create ``n`` synthetic flight records with the exact raw BTS column names."""
    rng = np.random.default_rng(seed)

    carriers = rng.choice(list(CARRIERS), n, p=np.array(list(CARRIERS.values())) / sum(CARRIERS.values()))
    codes = list(AIRPORTS)
    w = np.array([AIRPORTS[c][2] for c in codes], float)
    o_idx = rng.choice(len(codes), n, p=w / w.sum())
    d_idx = rng.choice(len(codes), n, p=w / w.sum())
    same = o_idx == d_idx
    d_idx[same] = (d_idx[same] + 1) % len(codes)  # an airport cannot fly to itself
    origin, dest = np.array(codes)[o_idx], np.array(codes)[d_idx]

    # Deterministic pseudo-distance per airport pair (symmetric)
    pair_seed = np.minimum(o_idx, d_idx) * 100 + np.maximum(o_idx, d_idx)
    distance = 150 + (pair_seed * 2654435761 % 2400)
    distance = np.where(np.isin(origin, ["HNL", "ANC"]) | np.isin(dest, ["HNL", "ANC"]), distance + 1500, distance)

    month = rng.integers(1, 13, n)
    dom = rng.integers(1, 29, n)
    fl_date = pd.to_datetime(dict(year=2024, month=month, day=dom))
    dow = fl_date.dt.dayofweek.to_numpy() + 1  # 1 = Monday ... 7 = Sunday (BTS convention)

    hour = rng.choice(24, n, p=HOUR_WEIGHTS / HOUR_WEIGHTS.sum())
    crs_dep = hour * 60 + rng.integers(0, 60, n)

    # --- Delay model: scale grows through the day, in summer and winter peaks, per carrier
    scale = (0.6 + 0.07 * hour) * np.vectorize(CARRIER_FACTOR.get)(carriers) * (1 + 0.25 * np.isin(month, [6, 7, 12, 1, 2]))
    dep_delay = np.round(-7 + rng.gamma(1.0, 4.2, n) * scale + (rng.random(n) < 0.03) * rng.exponential(90, n))
    taxi_out = np.round(rng.gamma(4, 4.5, n)).clip(4, 120)
    taxi_in = np.round(rng.gamma(3, 3, n)).clip(2, 60)
    air_est = distance / 7.6 + 12
    air_time = np.round(air_est + rng.normal(0, 7, n)).clip(20)
    crs_elapsed = np.round(air_est + 28)
    actual_elapsed = taxi_out + air_time + taxi_in
    arr_delay = dep_delay + (actual_elapsed - crs_elapsed)
    arr_delay = np.round(arr_delay).astype(float)
    crs_arr = crs_dep + crs_elapsed

    # --- Delay causes: only for arrivals >= 15 min late; minutes sum exactly to arr_delay
    cause_cols = ["carrier_delay", "weather_delay", "nas_delay", "security_delay", "late_aircraft_delay"]
    causes = np.zeros((n, 5))
    late = arr_delay >= 15
    shares = rng.dirichlet([2.2, 0.7, 1.6, 0.03, 3.0], late.sum())
    split = np.floor(shares * arr_delay[late, None])
    split[:, 4] += arr_delay[late] - split.sum(axis=1)  # remainder -> late aircraft
    causes[late] = split

    # --- Cancellations (higher in winter) and diversions
    p_cancel = 0.011 + 0.012 * np.isin(month, [12, 1, 2])
    cancelled = rng.random(n) < p_cancel
    diverted = (~cancelled) & (rng.random(n) < 0.0025)
    code = np.where(cancelled, rng.choice(list("ABCD"), n, p=[0.35, 0.40, 0.24, 0.01]), None)

    # --- Actual clock times (HHMM floats)
    dep_time = crs_dep + dep_delay
    wheels_off = dep_time + taxi_out
    wheels_on = wheels_off + air_time
    arr_time = wheels_on + taxi_in

    df = pd.DataFrame({
        "year": 2024, "month": month, "day_of_month": dom, "day_of_week": dow,
        "fl_date": fl_date.dt.strftime("%Y-%m-%d"),
        "op_unique_carrier": carriers, "op_carrier_fl_num": rng.integers(1, 7000, n).astype(float),
        "origin": origin, "origin_city_name": [AIRPORTS[c][0] for c in origin],
        "origin_state_nm": [AIRPORTS[c][1] for c in origin],
        "dest": dest, "dest_city_name": [AIRPORTS[c][0] for c in dest],
        "dest_state_nm": [AIRPORTS[c][1] for c in dest],
        "crs_dep_time": _to_hhmm(crs_dep), "dep_time": _to_hhmm(dep_time), "dep_delay": dep_delay,
        "taxi_out": taxi_out, "wheels_off": _to_hhmm(wheels_off), "wheels_on": _to_hhmm(wheels_on),
        "taxi_in": taxi_in, "crs_arr_time": _to_hhmm(crs_arr), "arr_time": _to_hhmm(arr_time),
        "arr_delay": arr_delay, "cancelled": cancelled.astype(int), "cancellation_code": code,
        "diverted": diverted.astype(int), "crs_elapsed_time": crs_elapsed, "actual_elapsed_time": actual_elapsed,
        "air_time": air_time, "distance": distance,
    })
    for i, c in enumerate(cause_cols):
        df[c] = causes[:, i]

    # Real-data behaviour: blanks for cancelled flights; diverted flights lack arrival info
    cancel_blank = ["dep_time", "dep_delay", "taxi_out", "wheels_off", "wheels_on", "taxi_in", "arr_time",
                    "arr_delay", "actual_elapsed_time", "air_time"]
    df.loc[cancelled, cancel_blank] = np.nan
    df.loc[diverted, ["arr_delay", "actual_elapsed_time", "air_time"]] = np.nan
    df.loc[cancelled | diverted, cause_cols] = 0.0

    # Sprinkle small random gaps in completed flights so the imputation step is exercised
    done_idx = df.index[~(cancelled | diverted)]
    for col in ("dep_time", "wheels_off", "wheels_on", "arr_time"):
        df.loc[rng.choice(done_idx, size=max(1, len(done_idx) // 800), replace=False), col] = np.nan
    return df
