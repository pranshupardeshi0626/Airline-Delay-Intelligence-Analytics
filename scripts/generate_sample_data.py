#!/usr/bin/env python
"""Generate a SYNTHETIC sample (same schema as the Kaggle file) for demos and CI.

    python scripts/generate_sample_data.py --rows 100000 --out data/raw/flight_random_1million.csv

WARNING: figures computed from this file are simulated, not real airline statistics.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from airline_delay.data.synthetic import generate_sample  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=100_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/raw/flight_random_1million.csv")
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    generate_sample(a.rows, a.seed).to_csv(out, index=False)
    print(f"Wrote {a.rows:,} synthetic rows -> {out}")


if __name__ == "__main__":
    main()
