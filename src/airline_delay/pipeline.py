"""End-to-end orchestration: raw CSV -> clean data -> features -> tables -> figures -> report."""
from __future__ import annotations

import json
from typing import Any, Dict

from airline_delay.analysis import insights, metrics
from airline_delay.config import load_config, resolve_path
from airline_delay.data.cleaning import clean_flights
from airline_delay.data.loader import load_raw_data, save_processed
from airline_delay.features.engineering import engineer_features
from airline_delay.features.outliers import summarize_outliers
from airline_delay.logging_utils import get_logger
from airline_delay.visualization import plots

log = get_logger(__name__)


def run_pipeline(config_path: str | None = None, nrows: int | None = None,
                 skip_figures: bool = False) -> Dict[str, Any]:
    """Execute the whole analytics pipeline.

    Parameters
    ----------
    config_path:
        Optional alternative YAML configuration.
    nrows:
        Read only the first *n* raw rows (fast smoke runs).
    skip_figures:
        Skip HTML chart generation (useful in CI).

    Returns
    -------
    dict with the headline KPIs and the output locations.
    """
    cfg = load_config(config_path)
    p = cfg["paths"]

    # 1) Ingest + validate
    raw = load_raw_data(resolve_path(p["raw_data"]), nrows=nrows)

    # 2) Clean (types, duplicates, timestamp imputation) + data-quality report
    clean, quality = clean_flights(raw, cfg)
    del raw  # free memory - the raw frame is ~1M rows x 35 cols

    # 3) Business features
    df = engineer_features(clean, cfg)
    quality["outliers"] = summarize_outliers(df, cfg)  # how much do outliers matter?
    save_processed(df, resolve_path(p["processed_data"]))
    qpath = resolve_path(p["data_quality_report"])
    qpath.parent.mkdir(parents=True, exist_ok=True)
    qpath.write_text(json.dumps(quality, indent=2), encoding="utf-8")

    # 4) KPI tables + CSV export
    kpis = {**metrics.network_kpis(df, cfg), **metrics.carryover_kpis(df, cfg)}
    tables = insights.build_tables(df, cfg)
    insights.export_tables(tables, resolve_path(p["tables_dir"]))

    # 5) Figures
    if not skip_figures:
        figs = plots.generate_all_figures(df, tables, cfg)
        plots.save_figures(figs, resolve_path(p["figures_dir"]))

    # 6) Narrative report
    insights.write_report(insights.render_report(df, tables, kpis, cfg, quality), resolve_path(p["report_file"]))

    log.info("Pipeline finished. Headline KPIs: %s", kpis)
    return {"kpis": kpis, "quality": quality, "report": str(resolve_path(p["report_file"]))}
