"""End-to-end smoke test: synthetic CSV -> all artefacts on disk."""
import yaml

from airline_delay.config import load_config
from airline_delay.data.synthetic import generate_sample
from airline_delay.pipeline import run_pipeline


def test_full_pipeline_creates_all_artifacts(tmp_path):
    raw = tmp_path / "raw.csv"
    generate_sample(6000, seed=1).to_csv(raw, index=False)

    cfg = load_config()
    cfg["paths"] = {
        "raw_data": str(raw), "interim_dir": str(tmp_path / "interim"),
        "processed_data": str(tmp_path / "clean.parquet"), "figures_dir": str(tmp_path / "figs"),
        "tables_dir": str(tmp_path / "tables"), "report_file": str(tmp_path / "report.md"),
        "data_quality_report": str(tmp_path / "dq.json"),
    }
    cfg["business_rules"].update(min_flights_airport=20, min_flights_route=5, min_flights_airline=20)
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    result = run_pipeline(str(cfg_file))

    assert (tmp_path / "clean.parquet").exists()
    assert (tmp_path / "report.md").read_text(encoding="utf-8").startswith("# Airline Delay Intelligence")
    assert len(list((tmp_path / "figs").glob("*.html"))) == 28
    assert (tmp_path / "tables" / "airline_kpis.csv").exists()
    assert 0 < result["kpis"]["ontime_pct"] <= 100
