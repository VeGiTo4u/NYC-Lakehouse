# Databricks notebook source

# ============================================================
# Bronze Loader: Restaurant Inspections
#
# Reads raw Parquet files from S3 landing zone using Databricks
# Autoloader (cloudFiles) and appends to Bronze Delta table.
#
# Source      : s3://nyc-lakehouse-store/raw/restaurant/
# Target      : {catalog}.bronze.restaurant_inspections
# Dataset     : NYC Open Data -- 43nn-pn8j
# Primary Key : camis + inspection_date + violation_code
#               (dedup handled in dbt Staging)
# Mode        : Append-only (no MERGE at Bronze)
#
# Note: One inspection date can have MULTIPLE rows for the same
# camis -- one row per violation. This is expected raw structure.
# Deduplication and grain resolution happen in dbt Staging.
#
# Architecture Reference:
#   High-Level Architecture.md -- Section 7.3 (Bronze Layer)
#   CLAUDE.md -- Section 3 (Bronze Layer)
# ============================================================

# COMMAND ----------

%run /Workspace/NYC-Lakehouse/scripts/bronze/utils

# COMMAND ----------

# -- Widgets -----------------------------------------------

# -- Widgets -----------------------------------------------

dbutils.widgets.text("catalog", "nyc-lakehouse", "Catalog Name")
dbutils.widgets.text("schema", "bronze", "Schema Name")
dbutils.widgets.text("s3_source_path", "", "S3 Source Path")
dbutils.widgets.text("s3_target_path", "", "S3 Delta Location")
dbutils.widgets.text("table_name", "", "Table Name")

catalog        = dbutils.widgets.get("catalog")
schema         = dbutils.widgets.get("schema")
s3_source_path = dbutils.widgets.get("s3_source_path")
s3_target_path = dbutils.widgets.get("s3_target_path")
table_name     = dbutils.widgets.get("table_name")

# COMMAND ----------

# -- Input Validation + Configuration ---------------------

s3_source_path, s3_target_path = validate_inputs(s3_source_path, s3_target_path, table_name)
full_table_name = build_table_name(catalog, schema, table_name)
CHECKPOINT_PATH = "s3://nyc-lakehouse-store/checkpoints/bronze/restaurant_inspections/"

# COMMAND ----------

# -- ETL Metadata -----------------------------------------

etl_meta = resolve_etl_metadata()

# COMMAND ----------

# -- Schema Setup -----------------------------------------

setup_bronze_schema(catalog, schema)

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

# -- Registration + Validation ----------------------------

if rows_written > 0:
    register_table(full_table_name, s3_target_path)
    post_write_validation_bronze(full_table_name, rows_written)
else:
    print("[INFO] No new data -- skipping registration and validation")

# COMMAND ----------

# -- Summary ----------------------------------------------

print_summary(
    label           = "RESTAURANT INSPECTIONS",
    full_table_name = full_table_name,
    s3_source_path  = s3_source_path,
    s3_target_path  = s3_target_path,
    etl_meta        = etl_meta,
    extra_info      = {
        "rows_written":    rows_written,
        "checkpoint_path": checkpoint_path,
        "dataset_id":      "43nn-pn8j",
    },
)
