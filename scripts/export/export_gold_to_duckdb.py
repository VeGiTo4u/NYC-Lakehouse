# Databricks notebook source

# ============================================================
# Gold → DuckDB Export (Atomic Write)
#
# Exports all four Gold mart tables into a single DuckDB file
# and uploads to S3. Streamlit reads this file once at startup
# into memory for instant, zero-cost filter responses.
#
# Why DuckDB (not direct Databricks SQL from Streamlit):
#   Gold marts are ~25k rows total. Querying a Databricks SQL
#   Warehouse on every filter click has 30-60s cold-start latency
#   and per-click warehouse cost. DuckDB in memory = instant.
#
# Atomic write pattern (prevents Streamlit from reading a partial file):
#   1. Export to gold_{timestamp}.duckdb (timestamped tmp file)
#   2. Upload to S3 as exports/gold_{timestamp}.duckdb
#   3. S3 copy_object → exports/gold_latest.duckdb  (atomic)
#   4. Delete timestamped tmp file from S3 (cleanup)
#
# Source  : nyc-lakehouse.marts.{mart_*}
# Target  : s3://nyc-lakehouse-store/exports/gold_latest.duckdb
#
# Architecture Reference:
#   High-Level Architecture.md -- Section 7.8 (DuckDB export)
# ============================================================

# COMMAND ----------

import boto3
import duckdb
import os
import tempfile
from datetime import datetime, timezone

# COMMAND ----------

# -- Widgets -----------------------------------------------

dbutils.widgets.text("catalog",   "nyc-lakehouse", "Catalog Name")
dbutils.widgets.text("schema",    "marts",          "Mart Schema Name")
dbutils.widgets.text("s3_bucket", "nyc-lakehouse-store", "S3 Bucket")
dbutils.widgets.text("s3_prefix", "exports",        "S3 Export Prefix")

catalog   = dbutils.widgets.get("catalog")
schema    = dbutils.widgets.get("schema")
s3_bucket = dbutils.widgets.get("s3_bucket")
s3_prefix = dbutils.widgets.get("s3_prefix").rstrip("/")

MART_TABLES = [
    "mart_neighborhood_pulse",
    "mart_safety_infrastructure_corr",
    "mart_top_complaints_by_borough",
    "mart_food_compliance",
]

# Audit columns added by dbt -- strip before export (not needed in Streamlit)
AUDIT_COLS = {"_gold_loaded_at", "_gold_model_name", "_gold_run_id"}

# COMMAND ----------

# -- Export Gold marts → local DuckDB file -----------------

timestamp    = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
tmp_filename = f"gold_{timestamp}.duckdb"
tmp_path     = os.path.join(tempfile.gettempdir(), tmp_filename)

print(f"Exporting {len(MART_TABLES)} mart tables to {tmp_path} ...")

conn = duckdb.connect(tmp_path)

for mart in MART_TABLES:
    full_name = f"`{catalog}`.`{schema}`.`{mart}`"
    print(f"  Reading {full_name} ...")

    df = spark.table(full_name).toPandas()

    # Strip dbt audit columns -- they add no dashboard value
    cols_to_drop = [c for c in df.columns if c in AUDIT_COLS]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    row_count = len(df)
    conn.execute(f"CREATE OR REPLACE TABLE {mart} AS SELECT * FROM df")
    print(f"  ✓ {mart}: {row_count} rows, {len(df.columns)} columns")

conn.close()

file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
print(f"\nDuckDB file size: {file_size_mb:.2f} MB")

# Sanity check -- warn if unreasonably large (something went wrong)
if file_size_mb > 200:
    raise ValueError(
        f"DuckDB export is {file_size_mb:.1f} MB -- expected <200 MB for Gold mart data. "
        "Check that mart tables haven't exploded in size."
    )

# COMMAND ----------

# -- Upload to S3 (atomic two-step) ------------------------
# Step 1: upload to timestamped key
# Step 2: S3 copy_object to gold_latest.duckdb (S3 copy is atomic from reader perspective)
# Step 3: delete the timestamped tmp key (keep exports/ clean)

s3 = boto3.client("s3")

tmp_s3_key    = f"{s3_prefix}/gold_{timestamp}.duckdb"
final_s3_key  = f"{s3_prefix}/gold_latest.duckdb"

print(f"\nUploading to s3://{s3_bucket}/{tmp_s3_key} ...")
s3.upload_file(tmp_path, s3_bucket, tmp_s3_key)
print("Upload complete.")

print(f"Atomically copying to s3://{s3_bucket}/{final_s3_key} ...")
s3.copy_object(
    Bucket=s3_bucket,
    CopySource={"Bucket": s3_bucket, "Key": tmp_s3_key},
    Key=final_s3_key,
)
print("Atomic copy complete.")

# Cleanup timestamped tmp key -- gold_latest.duckdb is the canonical file
s3.delete_object(Bucket=s3_bucket, Key=tmp_s3_key)
print(f"Deleted timestamped tmp key: {tmp_s3_key}")

# Cleanup local tmp file
os.remove(tmp_path)

# COMMAND ----------

# -- Summary -----------------------------------------------

print(f"""
=== Gold → DuckDB Export Summary ===
Tables exported : {', '.join(MART_TABLES)}
DuckDB size     : {file_size_mb:.2f} MB
S3 final key    : s3://{s3_bucket}/{final_s3_key}
Timestamp       : {timestamp}
=====================================
Streamlit loads this file once at startup via:
  duckdb.connect('/tmp/gold_latest.duckdb')
  (downloaded from S3 via @st.cache_resource)
""")
