# Databricks notebook source

# ============================================================
# Bronze Loader: DOB Permits
#
# Reads raw Parquet files from S3 landing zone using Databricks
# Autoloader (cloudFiles) and appends to Bronze Delta table.
#
# Source      : s3://nyc-lakehouse-store/raw/dob/
# Target      : {catalog}.bronze.dob_permits
# Dataset     : NYC Open Data -- ipu4-2q9a
# Primary Key : job__ + permit_sequence__ (dedup handled in dbt Staging)
# Mode        : Append-only (no MERGE at Bronze)
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
dbutils.widgets.text("s3_source_path", "", "S3 Source Path")
dbutils.widgets.text("s3_target_path", "", "S3 Delta Location")
dbutils.widgets.text("table_name", "", "Table Name")
dbutils.widgets.text(
    "checkpoint_path",
    "s3://nyc-lakehouse-store/checkpoints/bronze/dob_permits/",
    "Checkpoint Path",
)

catalog         = dbutils.widgets.get("catalog")
schema          = dbutils.widgets.get("schema")
s3_source_path  = dbutils.widgets.get("s3_source_path")
s3_target_path  = dbutils.widgets.get("s3_target_path")
table_name      = dbutils.widgets.get("table_name")
checkpoint_path = dbutils.widgets.get("checkpoint_path")

# COMMAND ----------

# -- Input Validation + Configuration ---------------------

s3_source_path, s3_target_path = validate_inputs(s3_source_path, s3_target_path, table_name)
full_table_name = build_table_name(catalog, schema, table_name)

# COMMAND ----------

# -- ETL Metadata -----------------------------------------

etl_meta = resolve_etl_metadata()

# COMMAND ----------

# -- Schema Setup + Registration --------------------------

setup_bronze_schema(catalog, schema)
register_table(full_table_name, s3_target_path)

# COMMAND ----------

# -- Autoloader Ingestion ---------------------------------

rows_written = load_bronze_autoloader(
    source_path     = s3_source_path,
    checkpoint_path = checkpoint_path,
    delta_location  = s3_target_path,
    etl_meta        = etl_meta,
    table_name      = table_name,
)

# COMMAND ----------

# -- Validation -------------------------------------------

if rows_written > 0:
    post_write_validation_bronze(
        full_table_name,
        rows_written,
        job_run_id=etl_meta["job_run_id"],
    )
else:
    print("[INFO] No new data -- skipping batch validation")

# COMMAND ----------

# -- Summary ----------------------------------------------

print_summary(
    label           = "DOB PERMITS",
    full_table_name = full_table_name,
    s3_source_path  = s3_source_path,
    s3_target_path  = s3_target_path,
    etl_meta        = etl_meta,
    extra_info      = {
        "rows_written":    rows_written,
        "checkpoint_path": checkpoint_path,
        "dataset_id":      "ipu4-2q9a",
    },
)
