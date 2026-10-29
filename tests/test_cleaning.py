"""Unit tests for the cleaning layer."""
import pandas as pd
import pytest

from airline_delay.data.cleaning import clean_flights, completed_mask, hhmm_to_minutes, impute_completed_flight_times
from airline_delay.data.loader import SchemaError, validate_schema


def test_hhmm_conversion_handles_edge_cases():
    s = pd.Series([0, 5, 1435, 2359, 2400, 1260, -5, None], dtype="float")
    out = hhmm_to_minutes(s).tolist()
    # 1260 (minutes=60) and -5 are invalid; 2400 wraps to midnight
    assert out[:5] == [0, 5, 14 * 60 + 35, 23 * 60 + 59, 0]
    assert pd.isna(out[5]) and pd.isna(out[6]) and pd.isna(out[7])


def test_schema_validation_fails_fast(raw_df):
    with pytest.raises(SchemaError):
        validate_schema(raw_df.drop(columns=["arr_delay"]))


def test_constant_year_dropped_and_cancellation_code_kept(clean_df):
    assert "year" not in clean_df.columns
    assert "cancellation_code" in clean_df.columns  # kept on purpose (cancellation reason)


def test_no_nulls_left_in_core_columns_for_completed_flights(clean_df):
    done = completed_mask(clean_df)
    for col in ["dep_time", "wheels_off", "wheels_on", "arr_time", "dep_delay", "arr_delay"]:
        assert clean_df.loc[done, col].isna().sum() == 0, col


def test_imputation_wraps_past_midnight_and_skips_cancelled():
    df = pd.DataFrame({
        "cancelled": [0, 1], "diverted": [0, 0],
        "crs_dep_time": pd.array([23 * 60 + 50, 600], dtype="Int64"),
        "dep_delay": pd.array([30, 10], dtype="Int64"),
        "dep_time": pd.array([pd.NA, pd.NA], dtype="Int64"),
        "taxi_out": pd.array([10, 10], dtype="Int64"),
        "wheels_off": pd.array([pd.NA, pd.NA], dtype="Int64"),
        "air_time": pd.array([60, 60], dtype="Int64"),
        "wheels_on": pd.array([pd.NA, pd.NA], dtype="Int64"),
        "taxi_in": pd.array([5, 5], dtype="Int64"),
        "arr_time": pd.array([pd.NA, pd.NA], dtype="Int64"),
    })
    out = impute_completed_flight_times(df)
    assert out.loc[0, "dep_time"] == 20          # 23:50 + 30 min -> 00:20 next day
    assert out.loc[0, "arr_time"] == 20 + 10 + 60 + 5
    assert pd.isna(out.loc[1, "dep_time"])       # cancelled flight untouched


def test_cleaning_is_idempotent_on_row_count(raw_df, cfg):
    df, report = clean_flights(raw_df, cfg)
    assert len(df) == report["rows_clean"] <= report["rows_raw"]
    assert report["cancelled_and_diverted"] == 0


def test_flight_number_has_no_decimal_suffix(clean_df):
    assert not clean_df["op_carrier_fl_num"].dropna().str.contains(r"\.").any()
