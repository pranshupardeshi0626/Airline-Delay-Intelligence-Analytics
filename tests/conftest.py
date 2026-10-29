"""Shared pytest fixtures (small synthetic dataset + config)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from airline_delay.config import load_config  # noqa: E402
from airline_delay.data.cleaning import clean_flights  # noqa: E402
from airline_delay.data.synthetic import generate_sample  # noqa: E402
from airline_delay.features.engineering import engineer_features  # noqa: E402


@pytest.fixture(scope="session")
def cfg():
    """Project configuration."""
    return load_config()


@pytest.fixture(scope="session")
def raw_df():
    """8k-row synthetic raw frame (same columns as the Kaggle file)."""
    return generate_sample(8000, seed=7)


@pytest.fixture(scope="session")
def clean_df(raw_df, cfg):
    """Cleaned frame."""
    df, _ = clean_flights(raw_df, cfg)
    return df


@pytest.fixture(scope="session")
def feat_df(clean_df, cfg):
    """Cleaned + engineered frame."""
    return engineer_features(clean_df, cfg)
