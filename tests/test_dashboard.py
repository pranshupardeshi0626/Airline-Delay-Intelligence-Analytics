"""Headless smoke tests for the Streamlit dashboard (uses Streamlit's AppTest, no browser needed)."""
import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from airline_delay.data.loader import save_processed  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


@pytest.fixture(scope="module")
def app(tmp_path_factory, feat_df):
    """Run the app against a small processed dataset (path injected via environment variable)."""
    import os
    path = tmp_path_factory.mktemp("dash") / "flights.parquet"
    save_processed(feat_df, path)
    os.environ["AIRLINE_DASHBOARD_DATA"] = str(path)
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    yield at
    os.environ.pop("AIRLINE_DASHBOARD_DATA", None)


def _cards(at):
    txt = " ".join(m.value for m in at.markdown if 'class="pass"' in m.value)
    return dict(re.findall(r'class="lbl">([^<]+)</div><div class="val[^"]*">([^<]+)<', txt))


def test_app_starts_without_errors(app):
    assert not app.exception


def test_overview_kpis_match_dataset(app, feat_df):
    cards = _cards(app)
    assert cards["Flights"] == f"{len(feat_df):,}"
    assert "%" in cards["On-time"]


def test_every_page_renders(app):
    radio = app.sidebar.radio[0]
    for page in radio.options:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, f"{page}: {app.exception[0].value if app.exception else ''}"
    app.sidebar.radio[0].set_value(radio.options[0]).run()


def test_filter_changes_flight_count_and_reset_restores_it(app, feat_df):
    airline = feat_df["airline_name"].value_counts().index[0]
    app.sidebar.multiselect[0].set_value([airline]).run()
    n_filtered = int(_cards(app)["Flights"].replace(",", ""))
    assert 0 < n_filtered < len(feat_df)
    [b for b in app.sidebar.button if "Reset" in b.label][0].click().run()
    assert _cards(app)["Flights"] == f"{len(feat_df):,}"
    assert not app.exception


def test_empty_selection_is_handled_gracefully(app, feat_df):
    airline = feat_df["airline_name"].value_counts().index[0]
    app.sidebar.multiselect[0].set_value([airline]).run()
    app.sidebar.multiselect[1].set_value(["Sat"]).run()
    app.sidebar.multiselect[2].set_value(["Red-eye (00-05)"]).run()
    for page in app.sidebar.radio[0].options:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page
    [b for b in app.sidebar.button if "Reset" in b.label][0].click().run()
