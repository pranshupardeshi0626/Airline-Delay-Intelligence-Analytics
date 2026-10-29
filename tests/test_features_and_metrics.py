"""Tests for feature engineering and KPI maths."""
import numpy as np

from airline_delay.analysis import metrics as m
from airline_delay.data.cleaning import completed_mask
from airline_delay.data.schema import DELAY_CAUSE_COLUMNS


def test_every_flight_has_exactly_one_known_status(feat_df):
    assert "Unknown" not in set(feat_df["arrival_status"])
    assert "Unknown" not in set(feat_df["departure_status"])


def test_cancelled_flights_never_count_as_on_time(feat_df):
    cancelled = feat_df["cancelled"] == 1
    assert feat_df.loc[cancelled, "is_arr_delayed"].isna().all()


def test_delay_flag_matches_threshold(feat_df, cfg):
    thr = cfg["business_rules"]["delay_threshold_minutes"]
    done = completed_mask(feat_df)
    expected = (feat_df.loc[done, "arr_delay"] >= thr).astype(int)
    assert (feat_df.loc[done, "is_arr_delayed"].astype(int) == expected).all()


def test_weekend_flag_and_hour_range(feat_df):
    assert set(feat_df.loc[feat_df.is_weekend == 1, "day_of_week"]) <= {6, 7}
    assert feat_df["scheduled_dep_hour"].between(0, 23).all()


def test_delay_causes_sum_to_arrival_delay(feat_df, cfg):
    thr = cfg["business_rules"]["delay_threshold_minutes"]
    d = feat_df[completed_mask(feat_df) & (feat_df["arr_delay"] >= thr)]
    assert (d[DELAY_CAUSE_COLUMNS].astype(float).sum(axis=1) == d["arr_delay"].astype(float)).all()


def test_cause_shares_sum_to_100(feat_df, cfg):
    s = m.delay_cause_summary(feat_df, cfg)
    assert abs(s["share_pct"].sum() - 100) < 0.1


def test_group_kpis_regression_no_int8_overflow(feat_df, cfg):
    """Regression: summing int8 flags per group once produced NEGATIVE cancel rates."""
    g = m.group_kpis(feat_df, "origin", cfg)
    assert (g["cancel_rate_pct"] >= 0).all() and (g["cancel_rate_pct"] <= 100).all()
    assert g["cancelled"].sum() == feat_df["cancelled"].astype("int64").sum()


def test_group_kpis_totals_reconcile_with_network(feat_df, cfg):
    g = m.group_kpis(feat_df, "airline_name", cfg)
    assert g["flights"].sum() == len(feat_df)
    net = m.network_kpis(feat_df, cfg)
    assert abs(100 * g["cancelled"].sum() / g["flights"].sum() - net["cancel_rate_pct"]) < 0.01


def test_min_flights_filter_removes_small_groups(feat_df, cfg):
    g = m.group_kpis(feat_df, "route", cfg, min_flights=50)
    assert (g["flights"] >= 50).all()


def test_ontime_and_delay_rate_are_complementary(feat_df, cfg):
    g = m.group_kpis(feat_df, "month", cfg)
    assert np.allclose(g["ontime_pct"] + g["delay_rate_pct"], 100, atol=0.02)


def test_carryover_kpis_are_percentages(feat_df, cfg):
    k = m.carryover_kpis(feat_df, cfg)
    for key in ("dep_late_arr_late_pct", "dep_ok_arr_late_pct", "arr_late_left_on_time_pct"):
        assert 0 <= k[key] <= 100
    assert k["dep_late_arr_late_pct"] > k["dep_ok_arr_late_pct"]      # delays carry through to arrival


def test_daily_kpis_reconcile_and_event_days_sorted(feat_df, cfg):
    daily = m.group_kpis(feat_df, "fl_date", cfg)
    assert daily["flights"].sum() == len(feat_df)
    top = m.disruption_days(daily, n=5, min_flights=1)
    assert top["cancel_rate_pct"].is_monotonic_decreasing
