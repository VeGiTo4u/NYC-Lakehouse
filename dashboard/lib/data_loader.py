"""
Load pre-aggregated KPI parquet files from dashboard/data/.

All dashboard pages read from this uniform local interface — no S3 or
warehouse connections at Streamlit runtime.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

EXPORT_FILES = [
    "neighborhood_pulse_summary.parquet",
    "borough_monthly_trends.parquet",
    "safety_infrastructure_corr.parquet",
    "food_compliance_overview.parquet",
    "complaint_type_rankings.parquet",
]

EXPORT_TABLE_NAMES = {
    "neighborhood_pulse_summary.parquet": "neighborhood_pulse_summary",
    "borough_monthly_trends.parquet": "borough_monthly_trends",
    "safety_infrastructure_corr.parquet": "safety_infrastructure_corr",
    "food_compliance_overview.parquet": "food_compliance_overview",
    "complaint_type_rankings.parquet": "complaint_type_rankings",
}


def data_dir() -> Path:
    return DATA_DIR


def manifest_path() -> Path:
    return DATA_DIR / "manifest.json"


@lru_cache(maxsize=1)
def load_manifest() -> Dict:
    path = manifest_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=len(EXPORT_FILES))
def load_export(filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Missing export '{filename}' in {DATA_DIR}. "
            "Run scripts/export/sync_kpi_from_s3.py or wait for the GitHub Actions sync."
        )
    return pd.read_parquet(path)


@lru_cache(maxsize=1)
def load_all_exports() -> Dict[str, pd.DataFrame]:
    return {
        EXPORT_TABLE_NAMES[filename]: load_export(filename)
        for filename in EXPORT_FILES
    }


def clear_cache() -> None:
    load_manifest.cache_clear()
    load_export.cache_clear()
    load_all_exports.cache_clear()
