"""Reading and writing datasets, plus schema validation."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from airline_delay.data.schema import REQUIRED_COLUMNS
from airline_delay.logging_utils import get_logger

log = get_logger(__name__)


class SchemaError(ValueError):
    """Raised when the input file does not contain the expected columns."""


def load_raw_data(path: str | Path, nrows: int | None = None) -> pd.DataFrame:
    """Load the raw flight CSV and validate its schema.

    Parameters
    ----------
    path:
        Location of ``flight_random_1million.csv`` (or any file with the same columns).
    nrows:
        Optional row limit, handy for quick smoke tests.

    Notes
    -----
    ``cancellation_code`` is forced to ``str`` because it is mostly empty and
    pandas would otherwise guess a float dtype.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Raw data not found at {path}.\n"
            "Download the Kaggle dataset 'hrishitpatil/flight-data-2024' into data/raw/ "
            "or generate a synthetic sample with: python scripts/generate_sample_data.py"
        )
    log.info("Reading raw data from %s", path)
    df = pd.read_csv(path, dtype={"cancellation_code": "str"}, low_memory=False, nrows=nrows)
    validate_schema(df)
    log.info("Loaded %s rows x %s columns", f"{len(df):,}", df.shape[1])
    return df


def validate_schema(df: pd.DataFrame) -> None:
    """Fail fast with a clear message if mandatory columns are missing."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"Input data is missing required columns: {missing}")


def save_processed(df: pd.DataFrame, path: str | Path) -> Path:
    """Persist the analysis-ready dataset (Parquet is ~10x smaller and keeps dtypes)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)
    log.info("Saved processed data -> %s", path)
    return path


def load_processed(path: str | Path) -> pd.DataFrame:
    """Load the analysis-ready dataset produced by the pipeline."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Processed data not found at {path}. Run scripts/run_pipeline.py first.")
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, low_memory=False)
