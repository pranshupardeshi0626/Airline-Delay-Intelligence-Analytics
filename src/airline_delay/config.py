"""Configuration loading utilities.

The whole pipeline is driven by ``config/config.yaml``. This module reads the
file once and exposes the contents as a plain dictionary together with helpers
to resolve relative paths against the project root.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

# Project root = two levels above this file (src/airline_delay/config.py -> repo root)
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH: Path = PROJECT_ROOT / "config" / "config.yaml"


def load_config(path: str | Path | None = None) -> Dict[str, Any]:
    """Read the YAML configuration file.

    Parameters
    ----------
    path:
        Optional path to a YAML file. Falls back to ``config/config.yaml``.

    Returns
    -------
    dict
        Parsed configuration.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    """
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def resolve_path(relative: str | Path) -> Path:
    """Resolve a (possibly relative) path from the config against the project root."""
    p = Path(relative)
    return p if p.is_absolute() else PROJECT_ROOT / p
