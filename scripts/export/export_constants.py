# ponytail: shared constants for export pipeline — single source of truth
# Used by export_kpi_parquet.py (Databricks) and sync_kpi_from_s3.py (local)

from typing import Dict, List

EXPORT_FILES: List[str] = [
    "neighborhood_pulse_summary.parquet",
    "borough_monthly_trends.parquet",
    "safety_infrastructure_corr.parquet",
    "food_compliance_overview.parquet",
    "complaint_type_rankings.parquet",
]

EXPORT_VALIDATION: Dict[str, Dict[str, object]] = {
    "neighborhood_pulse_summary.parquet": {
        "grain_keys": ["zip_code", "year_month"],
        "required_columns": [
            "zip_code",
            "year_month",
            "borough",
            "neighborhood_name",
            "neighborhood_pulse_score",
            "is_complete_month",
            "borough_avg_pulse_score",
            "city_avg_pulse_score",
            "pulse_score_prev_month",
            "pulse_score_mom_delta",
            "borough_pulse_rank",
            "borough_zip_count",
        ],
    },
    "borough_monthly_trends.parquet": {
        "grain_keys": ["borough", "year_month"],
        "required_columns": [
            "borough",
            "year_month",
            "year",
            "quarter",
            "month_name",
            "is_complete_month",
            "total_complaints",
            "total_arrests",
            "total_permits_issued",
            "total_inspections",
            "avg_pulse_score",
            "noise_complaint_count",
            "food_complaint_count",
            "construction_complaint_count",
            "felony_count",
            "misdemeanor_count",
            "critical_violation_count",
            "zip_code_count",
        ],
    },
    "safety_infrastructure_corr.parquet": {
        "grain_keys": ["zip_code", "year_month"],
        "required_columns": [
            "zip_code",
            "year_month",
            "total_arrests",
            "total_permits_issued",
            "arrests_per_permit",
            "felony_pct",
            "log_arrests",
            "log_permits",
        ],
    },
    "food_compliance_overview.parquet": {
        "grain_keys": ["zip_code", "year_month"],
        "required_columns": [
            "zip_code",
            "year_month",
            "total_inspections",
            "food_complaint_count",
            "food_complaints_per_inspection",
        ],
    },
    "complaint_type_rankings.parquet": {
        "grain_keys": ["borough", "year_month", "complaint_type"],
        "required_columns": [
            "borough",
            "year_month",
            "complaint_type",
            "complaint_count",
            "borough_rank",
            "pct_of_borough_total",
        ],
    },
}

MAX_EXPORT_BYTES: int = 10 * 1024 * 1024  # 10 MB sanity ceiling per export
