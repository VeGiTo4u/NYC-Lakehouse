# Databricks notebook source

# ============================================================
# Bronze Loader: NYPD Arrests
#
# Reads raw Parquet files from S3 landing zone using Databricks
# Autoloader (cloudFiles) and appends to Bronze Delta table.
#
# This notebook runs TWO Autoloader streams sequentially:
#   Stream 1 -- NYPD Historic (8h9b-rp9u): 2006 to end of prior year
#   Stream 2 -- NYPD YTD      (uip8-fykc): current calendar year
#
# Both streams append to the SAME nypd_arrests Delta table.
# Each stream has its own checkpoint to independently track
# which files have been processed.
#
# Source (1)  : s3://nyc-lakehouse-store/raw/nypd_historic/
# Source (2)  : s3://nyc-lakehouse-store/raw/nypd_ytd/
# Target      : {catalog}.bronze.nypd_arrests
# Primary Key : arrest_key (dedup handled in dbt Staging)
# Mode        : Append-only (no MERGE at Bronze)
#
# Why two streams into one table:
#   Per the architecture doc (Section 3), the Historic dataset
#   covers 2006 to end of prior calendar year and the YTD dataset
#   covers the current year. Both share identical schemas. Unioning
#   them at Bronze provides complete temporal coverage in a single
#   table for downstream dbt Staging to deduplicate and transform.
#
# Architecture Reference:
#   High-Level Architecture.md -- Section 7.3 (Bronze Layer)
#   CLAUDE.md -- Section 3 (Bronze Layer)
# ============================================================

# COMMAND ----------

%run /Workspace/NYC-Lakehouse/scripts/bronze/utils

# COMMAND ----------

# -- Widgets -----------------------------------------------

dbutils.widgets.text("catalog", "nyc-lakehouse", "Catalog Name")
dbutils.widgets.text("schema", "bronze", "Schema Name")
dbutils.widgets.text("checkpoint_path_historic", "s3://nyc-lakehouse-store/checkpoints/bronze/nypd_historic/","Checkpoint Historic")
dbutils.widgets.text("checkpoint_path_ytd", "s3://nyc-lakehouse-store/checkpoints/bronze/nypd_ytd/", "Checkpoint YTD")
dbutils.widgets.text("s3_source_path_historic", "", "S3 Source Historic")
dbutils.widgets.text("s3_source_path_ytd", "", "S3 Source YTD")
dbutils.widgets.text("s3_target_path", "", "S3 Delta Location")
dbutils.widgets.text("table_name", "", "Table Name")

catalog                  = dbutils.widgets.get("catalog")
schema                   = dbutils.widgets.get("schema")
s3_target_path           = dbutils.widgets.get("s3_target_path")
table_name               = dbutils.widgets.get("table_name")
s3_source_path_historic  = dbutils.widgets.get("s3_source_path_historic")
s3_source_path_ytd       = dbutils.widgets.get("s3_source_path_ytd")
checkpoint_path_historic = dbutils.widgets.get("checkpoint_path_historic")
checkpoint_path_ytd      = dbutils.widgets.get("checkpoint_path_ytd")

# COMMAND ----------

# -- Input Validation + Configuration ---------------------
# NYPD has two source paths -- validate each against the shared target.

s3_source_path_historic, s3_target_path = validate_inputs(s3_source_path_historic, s3_target_path, table_name)
s3_source_path_ytd, _ = validate_inputs(s3_source_path_ytd, s3_target_path, table_name)
full_table_name = build_table_name(catalog, schema, table_name)

# COMMAND ----------

# -- ETL Metadata -----------------------------------------

etl_meta = resolve_etl_metadata()

# COMMAND ----------

# -- Schema Setup + Registration --------------------------

setup_bronze_schema(catalog, schema)
register_table(full_table_name, s3_target_path)

# COMMAND ----------

# -- Stream 1: NYPD Historic ------------------------------
# Source: 8h9b-rp9u -- covers 2006 to end of prior calendar year.

print("=" * 60)
print("STREAM 1: NYPD Historic")
print("=" * 60)

rows_historic = load_bronze_autoloader(
    source_path     = s3_source_path_historic,
    checkpoint_path = checkpoint_path_historic,
    delta_location  = s3_target_path,
    etl_meta        = etl_meta,
    table_name      = table_name,
)

# COMMAND ----------

# -- Stream 2: NYPD Year-to-Date --------------------------
# Source: uip8-fykc -- covers the current calendar year.

print("=" * 60)
print("STREAM 2: NYPD Year-to-Date")
print("=" * 60)

rows_ytd = load_bronze_autoloader(
    source_path     = s3_source_path_ytd,
    checkpoint_path = checkpoint_path_ytd,
    delta_location  = s3_target_path,
    etl_meta        = etl_meta,
    table_name      = table_name,
)

# COMMAND ----------

# -- Registration + Validation ----------------------------
# Table registered above before ingestion. Validation checks
# the combined table for rows written in this job run.

rows_total = max(rows_historic, 0) + max(rows_ytd, 0)

if rows_total > 0:
    post_write_validation_bronze(
        full_table_name,
        rows_total,
        job_run_id=etl_meta["job_run_id"],
    )
else:
    print("[INFO] No new data from either stream -- skipping batch validation")

# COMMAND ----------

# -- Summary ----------------------------------------------

print_summary(
    label           = "NYPD ARRESTS",
    full_table_name = full_table_name,
    s3_source_path  = f"historic: {s3_source_path_historic}\nytd:      {s3_source_path_ytd}",
    s3_target_path  = s3_target_path,
    etl_meta        = etl_meta,
    extra_info      = {
        "rows_historic":          rows_historic,
        "rows_ytd":               rows_ytd,
        "rows_total":             rows_total,
        "checkpoint_historic":    checkpoint_path_historic,
        "checkpoint_ytd":         checkpoint_path_ytd,
        "dataset_id_historic":    "8h9b-rp9u",
        "dataset_id_ytd":         "uip8-fykc",
    },
)
