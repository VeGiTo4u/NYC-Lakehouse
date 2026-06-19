# Databricks notebook source

# ============================================================
# KPI Pre-Aggregation Export
#
# Reads 4 Gold mart tables, computes 5 pre-aggregated KPI
# DataFrames, and writes them as Parquet files to S3 for the
# Streamlit dashboard serving layer.
#
# Source tables : gold.mart_neighborhood_pulse
#                 gold.mart_safety_infrastructure_corr
#                 gold.mart_food_compliance
#                 gold.mart_top_complaints_by_borough
# Target        : s3://nyc-lakehouse-store/exports/kpi/
#
# Architecture Reference:
#   High-Level Architecture.md -- Section 7.8 (Presentation)
#   Phase 1 KPI Pre-Aggregation Export Script
# ============================================================

# COMMAND ----------

"""
KPI export notebook — pre-aggregates Gold marts into dashboard-ready
Parquet files. Audit columns from dbt are stripped; window/rank logic
is applied here so Streamlit only renders at query time.
"""

from datetime import datetime, timezone
from typing import Dict, List

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# COMMAND ----------

# -- Widgets -----------------------------------------------
# Parameterized for dev / staging / prod without code changes.

dbutils.widgets.text("catalog", "nyc-lakehouse", "Catalog Name")
dbutils.widgets.text("schema", "silver_gold", "Schema Name")
dbutils.widgets.text(
    "s3_export_base",
    "s3://nyc-lakehouse-store/exports/kpi/",
    "S3 Export Base Path",
)

catalog        = dbutils.widgets.get("catalog")
schema         = dbutils.widgets.get("schema")
s3_export_base = dbutils.widgets.get("s3_export_base")

# COMMAND ----------

# -- Configuration -----------------------------------------

GOLD_AUDIT_COLUMNS: List[str] = [
    "_gold_loaded_at",
    "_gold_model_name",
    "_gold_run_id",
]

SOURCE_TABLES: Dict[str, str] = {
    "mart_neighborhood_pulse":           "mart_neighborhood_pulse",
    "mart_safety_infrastructure_corr":   "mart_safety_infrastructure_corr",
    "mart_food_compliance":              "mart_food_compliance",
    "mart_top_complaints_by_borough":    "mart_top_complaints_by_borough",
}

EXPORT_FILES: List[str] = [
    "neighborhood_pulse_summary.parquet",
    "borough_monthly_trends.parquet",
    "safety_infrastructure_corr.parquet",
    "food_compliance_overview.parquet",
    "complaint_type_rankings.parquet",
]

MAX_EXPORT_BYTES: int = 10 * 1024 * 1024  # 10 MB sanity ceiling per export

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

run_timestamp: str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

if not s3_export_base.startswith("s3://"):
    raise ValueError(f"CONFIGURATION ERROR: Invalid export base path '{s3_export_base}'")

if not s3_export_base.endswith("/"):
    s3_export_base += "/"

staged_export_prefix: str = f"{s3_export_base}{run_timestamp}/"
latest_export_prefix: str = f"{s3_export_base}latest/"

print("[INFO] Export configuration resolved:")
print(f"  Catalog              : {catalog}")
print(f"  Schema               : {schema}")
print(f"  S3 export base       : {s3_export_base}")
print(f"  Staged prefix        : {staged_export_prefix}")
print(f"  Latest prefix        : {latest_export_prefix}")
print(f"  Run timestamp (UTC)  : {run_timestamp}")

# COMMAND ----------

# ------------------------------------------------------------
# read_gold_table
# ------------------------------------------------------------
def read_gold_table(table_key: str) -> DataFrame:
    """
    Reads a Gold mart table via spark.table() and strips dbt audit columns.

    Parameters
    ----------
    table_key : str
        Key in SOURCE_TABLES mapping the logical mart name.

    Returns
    -------
    DataFrame
        Mart data without _gold_* audit metadata columns.
    """
    table_name = SOURCE_TABLES[table_key]
    full_table_name = f"`{catalog}`.`{schema}`.`{table_name}`"

    print(f"[INFO] Reading Gold table: {full_table_name}")
    df = spark.table(full_table_name)

    audit_cols_present = [c for c in GOLD_AUDIT_COLUMNS if c in df.columns]
    if audit_cols_present:
        df = df.drop(*audit_cols_present)
        print(f"[INFO] Dropped audit columns: {', '.join(audit_cols_present)}")
    else:
        print("[INFO] No audit columns present — pass-through as-is")

    row_count = df.count()
    print(f"[INFO] Loaded {row_count:,} rows from {full_table_name}")

    if row_count == 0:
        raise ValueError(f"FAILED: Source table '{full_table_name}' returned 0 rows")

    return df

# COMMAND ----------

# ------------------------------------------------------------
# build_neighborhood_pulse_summary
# ------------------------------------------------------------
def build_neighborhood_pulse_summary(df: DataFrame) -> DataFrame:
    """
    Zip-level KPI summary with borough/city rollups, MoM delta, and rank.

    Source: mart_neighborhood_pulse
    Adds window-derived context columns for the Neighborhood Explorer page.
    """
    w_borough_month = Window.partitionBy("borough", "year_month")
    w_city_month = Window.partitionBy("year_month")
    w_zip_month = Window.partitionBy("zip_code").orderBy("year_month")
    w_borough_rank = Window.partitionBy("borough", "year_month").orderBy(
        F.col("neighborhood_pulse_score").desc()
    )

    result = (
        df
        .withColumn(
            "borough_avg_pulse_score",
            F.round(F.avg("neighborhood_pulse_score").over(w_borough_month), 2),
        )
        .withColumn(
            "city_avg_pulse_score",
            F.round(F.avg("neighborhood_pulse_score").over(w_city_month), 2),
        )
        .withColumn(
            "pulse_score_prev_month",
            F.lag("neighborhood_pulse_score").over(w_zip_month),
        )
        .withColumn(
            "pulse_score_mom_delta",
            F.round(
                F.col("neighborhood_pulse_score") - F.col("pulse_score_prev_month"),
                2,
            ),
        )
        .withColumn("borough_pulse_rank", F.rank().over(w_borough_rank))
        .withColumn("borough_zip_count", F.count(F.lit(1)).over(w_borough_month))
    )

    print(f"[SUCCESS] Built neighborhood_pulse_summary: {result.count():,} rows")
    return result

# COMMAND ----------

# ------------------------------------------------------------
# build_borough_monthly_trends
# ------------------------------------------------------------
def build_borough_monthly_trends(df: DataFrame) -> DataFrame:
    """
    Borough-level monthly aggregates for time-series charts.

    Source: mart_neighborhood_pulse
    Rolls ~25K zip rows down to ~5 boroughs x N months.
    """
    result = (
        df
        .groupBy("borough", "year_month")
        .agg(
            F.first("year", ignorenulls=True).alias("year"),
            F.first("quarter", ignorenulls=True).alias("quarter"),
            F.first("month_name", ignorenulls=True).alias("month_name"),
            F.first("is_complete_month", ignorenulls=True).alias("is_complete_month"),
            F.sum("total_complaints").alias("total_complaints"),
            F.sum("total_arrests").alias("total_arrests"),
            F.sum("total_permits_issued").alias("total_permits_issued"),
            F.sum("total_inspections").alias("total_inspections"),
            F.round(F.avg("neighborhood_pulse_score"), 2).alias("avg_pulse_score"),
            F.sum("noise_complaint_count").alias("noise_complaint_count"),
            F.sum("food_complaint_count").alias("food_complaint_count"),
            F.sum("construction_complaint_count").alias("construction_complaint_count"),
            F.sum("felony_count").alias("felony_count"),
            F.sum("misdemeanor_count").alias("misdemeanor_count"),
            F.sum("critical_violation_count").alias("critical_violation_count"),
            F.countDistinct("zip_code").alias("zip_code_count"),
        )
        .orderBy("year_month", "borough")
    )

    print(f"[SUCCESS] Built borough_monthly_trends: {result.count():,} rows")
    return result

# COMMAND ----------

# ------------------------------------------------------------
# build_safety_infrastructure_corr
# ------------------------------------------------------------
def build_safety_infrastructure_corr(df: DataFrame) -> DataFrame:
    """
    Zip-level arrests vs permits correlation with log-scaled scatter axes.

    Source: mart_safety_infrastructure_corr
    """
    result = (
        df
        .withColumn("log_arrests", F.round(F.log10(F.col("total_arrests") + F.lit(1)), 4))
        .withColumn(
            "log_permits",
            F.round(F.log10(F.col("total_permits_issued") + F.lit(1)), 4),
        )
    )

    print(f"[SUCCESS] Built safety_infrastructure_corr: {result.count():,} rows")
    return result

# COMMAND ----------

# ------------------------------------------------------------
# build_food_compliance_overview
# ------------------------------------------------------------
def build_food_compliance_overview(df: DataFrame) -> DataFrame:
    """
    Zip-level food compliance passthrough.

    Source: mart_food_compliance
    Maintains uniform dashboard/data/*.parquet interface — no transforms needed.
    """
    row_count = df.count()
    print(f"[SUCCESS] Built food_compliance_overview: {row_count:,} rows (passthrough)")
    return df

# COMMAND ----------

# ------------------------------------------------------------
# build_complaint_type_rankings
# ------------------------------------------------------------
def build_complaint_type_rankings(df: DataFrame) -> DataFrame:
    """
    Borough complaint type rankings — top 15 per borough+month only.

    Source: mart_top_complaints_by_borough
    """
    result = df.filter(F.col("borough_rank") <= F.lit(15))

    print(f"[SUCCESS] Built complaint_type_rankings: {result.count():,} rows (top 15 filter)")
    return result

# COMMAND ----------

# ------------------------------------------------------------
# write_parquet_to_s3
# ------------------------------------------------------------
def write_parquet_to_s3(
    df: DataFrame,
    export_filename: str,
    staged_prefix: str,
    latest_prefix: str,
) -> Dict[str, str]:
    """
    Writes a DataFrame to a timestamped S3 prefix, then copies to latest/.

    Atomic write pattern:
      1. Write to exports/kpi/{timestamp}/{file}.parquet/
      2. Copy to   exports/kpi/latest/{file}.parquet/

    Returns paths for summary logging.
    """
    staged_path = f"{staged_prefix}{export_filename}"
    latest_path = f"{latest_prefix}{export_filename}"

    print(f"[INFO] Writing staged export: {staged_path}")
    (
        df.coalesce(1)
        .write
        .mode("overwrite")
        .option("compression", "snappy")
        .parquet(staged_path)
    )

    print(f"[INFO] Promoting export to latest: {latest_path}")
    if _path_exists(latest_path):
        dbutils.fs.rm(latest_path, recurse=True)

    dbutils.fs.cp(staged_path, latest_path, recurse=True)
    print(f"[SUCCESS] Export promoted: {export_filename}")

    return {
        "export_filename": export_filename,
        "staged_path": staged_path,
        "latest_path": latest_path,
    }

# COMMAND ----------

# ------------------------------------------------------------
# _path_exists / _get_path_size_bytes  (internal helpers)
# ------------------------------------------------------------
def _path_exists(path: str) -> bool:
    """Returns True if an S3/DBFS path exists."""
    try:
        dbutils.fs.ls(path)
        return True
    except Exception:
        return False


def _get_path_size_bytes(path: str) -> int:
    """Recursively sums file sizes under a path."""
    total = 0
    for entry in dbutils.fs.ls(path):
        if entry.isDir():
            total += _get_path_size_bytes(entry.path)
        else:
            total += entry.size
    return total

# COMMAND ----------

# ------------------------------------------------------------
# validate_exports
# ------------------------------------------------------------
def validate_exports(
    exports: Dict[str, DataFrame],
    write_results: Dict[str, Dict[str, str]],
) -> None:
    """
    Validates row counts, required columns, grain-key NULLs, and file sizes.

    Raises ValueError on any failed check.
    """
    print("[INFO] Starting export validation")
    all_passed = True

    for export_filename, df in exports.items():
        validation_cfg = EXPORT_VALIDATION[export_filename]
        grain_keys: List[str] = validation_cfg["grain_keys"]  # type: ignore[assignment]
        required_columns: List[str] = validation_cfg["required_columns"]  # type: ignore[assignment]

        row_count = df.count()
        if row_count <= 0:
            print(f"[FAIL] {export_filename}: row count must be > 0 (got {row_count})")
            all_passed = False
        else:
            print(f"[PASS] {export_filename}: row count = {row_count:,}")

        missing_columns = [c for c in required_columns if c not in df.columns]
        if missing_columns:
            print(f"[FAIL] {export_filename}: missing columns {missing_columns}")
            all_passed = False
        else:
            print(f"[PASS] {export_filename}: required columns present")

        null_exprs = [
            F.count(F.when(F.col(k).isNull(), F.lit(1))).alias(k)
            for k in grain_keys
        ]
        null_row = df.select(*null_exprs).collect()[0]
        for key in grain_keys:
            null_count = null_row[key]
            if null_count > 0:
                print(f"[FAIL] {export_filename}: {key} has {null_count:,} NULLs")
                all_passed = False
            else:
                print(f"[PASS] {export_filename}: {key} has no NULLs")

        latest_path = write_results[export_filename]["latest_path"]
        if not _path_exists(latest_path):
            print(f"[FAIL] {export_filename}: latest path not found ({latest_path})")
            all_passed = False
            continue

        size_bytes = _get_path_size_bytes(latest_path)
        size_mb = size_bytes / (1024 * 1024)
        if size_bytes >= MAX_EXPORT_BYTES:
            print(
                f"[FAIL] {export_filename}: size {size_mb:.2f} MB exceeds "
                f"{MAX_EXPORT_BYTES / (1024 * 1024):.0f} MB limit"
            )
            all_passed = False
        else:
            print(f"[PASS] {export_filename}: size {size_mb:.2f} MB (< 10 MB)")

    if not all_passed:
        raise ValueError("FAILED: One or more export validation checks did not pass")

    print("[SUCCESS] All export validation checks passed")

# COMMAND ----------

# ------------------------------------------------------------
# print_summary
# ------------------------------------------------------------
def print_summary(
    write_results: Dict[str, Dict[str, str]],
    export_row_counts: Dict[str, int],
    run_ts: str,
    s3_base: str,
) -> None:
    """Prints a standardized run summary for KPI exports."""
    print("\n" + "=" * 70)
    print("KPI PRE-AGGREGATION EXPORT SUMMARY")
    print("=" * 70)
    print(f"Catalog              : {catalog}")
    print(f"Schema               : {schema}")
    print(f"S3 export base       : {s3_base}")
    print(f"Run timestamp (UTC)  : {run_ts}")
    print(f"Latest prefix        : {s3_base}latest/")
    print("\nExports")
    for export_filename in EXPORT_FILES:
        paths = write_results[export_filename]
        rows = export_row_counts[export_filename]
        print(f"  {export_filename}")
        print(f"    Rows         : {rows:,}")
        print(f"    Staged path  : {paths['staged_path']}")
        print(f"    Latest path  : {paths['latest_path']}")
    print("=" * 70)
    print("[END] KPI export completed successfully")
    print("=" * 70)

# COMMAND ----------

# -- Main Execution ----------------------------------------

print("[START] KPI pre-aggregation export")

pulse_df = read_gold_table("mart_neighborhood_pulse")
safety_df = read_gold_table("mart_safety_infrastructure_corr")
food_df = read_gold_table("mart_food_compliance")
complaints_df = read_gold_table("mart_top_complaints_by_borough")

exports: Dict[str, DataFrame] = {
    "neighborhood_pulse_summary.parquet": build_neighborhood_pulse_summary(pulse_df),
    "borough_monthly_trends.parquet": build_borough_monthly_trends(pulse_df),
    "safety_infrastructure_corr.parquet": build_safety_infrastructure_corr(safety_df),
    "food_compliance_overview.parquet": build_food_compliance_overview(food_df),
    "complaint_type_rankings.parquet": build_complaint_type_rankings(complaints_df),
}

write_results: Dict[str, Dict[str, str]] = {}
export_row_counts: Dict[str, int] = {}

for export_filename, export_df in exports.items():
    export_row_counts[export_filename] = export_df.count()
    write_results[export_filename] = write_parquet_to_s3(
        df=export_df,
        export_filename=export_filename,
        staged_prefix=staged_export_prefix,
        latest_prefix=latest_export_prefix,
    )

validate_exports(exports, write_results)

print_summary(
    write_results=write_results,
    export_row_counts=export_row_counts,
    run_ts=run_timestamp,
    s3_base=s3_export_base,
)
