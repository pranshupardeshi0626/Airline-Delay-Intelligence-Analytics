"""Tests for the outlier policy: flag + winsorize, never delete."""
import pandas as pd

from airline_delay.data.cleaning import clean_flights, completed_mask
from airline_delay.features.engineering import engineer_features
from airline_delay.features.outliers import summarize_outliers


def _with_extreme(raw_df, cfg):
    """Inject a 3,000-minute delay into a copy of the raw data."""
    raw = raw_df.copy()
    i = raw.index[(raw.cancelled == 0) & (raw.diverted == 0)][0]
    raw.loc[i, ["dep_delay", "arr_delay"]] = [3000.0, 3000.0]
    clean, _ = clean_flights(raw, cfg)
    return engineer_features(clean, cfg), i


def test_no_rows_are_dropped_by_outlier_logic(raw_df, cfg):
    df, _ = _with_extreme(raw_df, cfg)
    assert len(df) == len(raw_df)


def test_extreme_delay_flagged_and_winsorized(raw_df, cfg):
    df, i = _with_extreme(raw_df, cfg)
    assert df.loc[i, "is_extreme_delay"] == 1
    assert df.loc[i, "arr_delay"] == 3000                       # raw value preserved
    assert df.loc[i, "arr_delay_w"] < 3000                       # capped copy used for rankings


def test_winsorized_mean_not_above_raw_mean_for_right_skew(feat_df):
    done = completed_mask(feat_df)
    assert feat_df.loc[done, "arr_delay_w"].mean() <= feat_df.loc[done, "arr_delay"].astype(float).mean() + 1e-9


def test_cancelled_flights_never_flagged_extreme(feat_df):
    assert (feat_df.loc[feat_df.cancelled == 1, "is_extreme_delay"] == 0).all()


def test_summary_keys_and_ranges(feat_df, cfg):
    s = summarize_outliers(feat_df, cfg)
    assert 0 <= s["extreme_delay_share_of_positive_delay_minutes_pct"] <= 100
    assert s["extreme_delay_flights"] == int(feat_df["is_extreme_delay"].sum())


def test_speed_anomaly_flag():
    # impossible 1,000 mph implied speed must be flagged
    from airline_delay.config import load_config
    from airline_delay.features.outliers import add_outlier_features
    cfg = load_config()
    df = pd.DataFrame({
        "cancelled": [0], "diverted": [0], "arr_delay": pd.array([5], dtype="Int64"),
        "dep_delay": pd.array([5], dtype="Int64"), "air_time": pd.array([60], dtype="Int64"),
        "distance": pd.array([1000], dtype="Int64"), "taxi_out": pd.array([10], dtype="Int64"),
        "taxi_in": pd.array([5], dtype="Int64"), "dep_time": pd.array([605], dtype="Int64"),
        "crs_dep_time": pd.array([600], dtype="Int64"), "arr_time": pd.array([700], dtype="Int64"),
        "crs_arr_time": pd.array([695], dtype="Int64"),
    })
    out = add_outlier_features(df, cfg)
    assert out.loc[0, "is_speed_anomaly"] == 1
