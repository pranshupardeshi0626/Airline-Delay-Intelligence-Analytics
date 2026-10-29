#!/usr/bin/env python
"""Command-line entry point.

Examples
--------
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --nrows 100000 --skip-figures
    python scripts/run_pipeline.py --config config/config.yaml
"""
import argparse
import sys
from pathlib import Path

# Allow running without `pip install -e .`
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from airline_delay.pipeline import run_pipeline  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Airline Delay Intelligence pipeline.")
    parser.add_argument("--config", default=None, help="Path to YAML config (default: config/config.yaml)")
    parser.add_argument("--nrows", type=int, default=None, help="Only read the first N raw rows")
    parser.add_argument("--skip-figures", action="store_true", help="Skip HTML chart generation")
    args = parser.parse_args()
    run_pipeline(args.config, nrows=args.nrows, skip_figures=args.skip_figures)


if __name__ == "__main__":
    main()
