# Databricks notebook source

# ============================================================
# bronze_utils
# Shared utility functions for all Bronze layer notebooks.
#
# Usage in each Bronze notebook:
#   %run ./bronze_utils
#
# Functions provided:
#   resolve_etl_metadata()           -- job/run context resolution
#   validate_inputs()                -- S3 path + table name checks
#   build_table_name()               -- fully qualified Unity Catalog name
#   setup_bronze_schema()            -- create catalog + schema if not exist
#   append_etl_metadata()            -- 7 ETL columns (4 architecture + 3 audit)
#   load_bronze_autoloader()         -- core Autoloader cloudFiles ingestion
#   register_table()                 -- CREATE TABLE IF NOT EXISTS USING DELTA LOCATION
#   _read_streaming_metrics()        -- rows committed from streaming query (internal)
#   post_write_validation_bronze()   -- NULL metadata check
#   print_summary()                  -- standardized run summary
#
# Architecture Reference:
#   High-Level Architecture.md -- Section 7.3 (Bronze Layer)
#   CLAUDE.md -- Section 3 (Bronze Layer)
# ============================================================

# COMMAND ----------

import os
from datetime import datetime, timezone
from pyspark.sql import functions as F
from pyspark.sql import DataFrame
from pyspark.sql.utils import AnalysisException
from typing import Dict, Any

# COMMAND ----------

# ------------------------------------------------------------
# resolve_etl_metadata
# ------------------------------------------------------------
def resolve_etl_metadata() -> Dict[str, str]:
    """
    Resolves job-level ETL metadata from Databricks notebook context.

    Uses dbruntime.databricks_repl_context -- the stable Python-native
    API (DBR 14.1+). Works on all cluster modes including Unity Catalog
    Shared Access Mode where dbutils.notebook.entry_point raises
    Py4JSecurityException.

    Resolved once at notebook startup -- not inside loops -- so all
    rows in a given batch share identical job-level metadata.

    Returns:
        dict with keys: job_run_id, notebook_path, source_system
    """
    from dbruntime.databricks_repl_context import get_context

    _ctx = get_context()

    job_id        = _ctx.jobId        or os.environ.get("DATABRICKS_JOB_ID", "INTERACTIVE")
    run_id        = _ctx.currentRunId or "INTERACTIVE"
    job_run_id    = f"{job_id}_{run_id}"
    notebook_path = _ctx.notebookPath or "UNKNOWN"
    source_system = "NYC_OPEN_DATA"

    print("[INFO] ETL metadata resolved:")
    print(f"  _job_run_id    : {job_run_id}")
    print(f"  _notebook_path : {notebook_path}")
    print(f"  _source_system : {source_system}")

    return {
        "job_run_id":    job_run_id,
        "notebook_path": notebook_path,
        "source_system": source_system,
    }

# COMMAND ----------

# ------------------------------------------------------------
# validate_inputs
# ------------------------------------------------------------
def validate_inputs(
    s3_source_path: str,
    s3_target_path: str,
    table_name:     str
) -> tuple:
    """
    Validates and normalizes widget inputs.
    Fails fast on misconfigured jobs before any Spark work is done.

    Returns:
        (normalized_s3_source_path, normalized_s3_target_path)
        Both guaranteed to have a trailing slash.
    """
    if not s3_source_path or not s3_source_path.startswith("s3://"):
        raise ValueError(f"CONFIGURATION ERROR: Invalid source path '{s3_source_path}'")

    if not s3_target_path or not s3_target_path.startswith("s3://"):
        raise ValueError(f"CONFIGURATION ERROR: Invalid target path '{s3_target_path}'")

    if not table_name:
        raise ValueError("CONFIGURATION ERROR: table_name not provided")

    if not s3_source_path.endswith("/"):
        s3_source_path += "/"

    if not s3_target_path.endswith("/"):
        s3_target_path += "/"

    print("[INFO] Input validation passed")
    return s3_source_path, s3_target_path

# COMMAND ----------

# ------------------------------------------------------------
# build_table_name
# ------------------------------------------------------------
def build_table_name(catalog: str, schema: str, table: str) -> str:
    """
    Builds a fully qualified Unity Catalog table name.

    Backticks are applied to the table identifier to support names
    that start with digits (e.g. 311_requests). Catalog and schema
    are also backticked for defensive consistency.

    Returns:
        "`<catalog>`.`<schema>`.`<table>`"
    """
    full_name = f"`{catalog}`.`{schema}`.`{table}`"
    print(f"[INFO] Target table : {full_name}")
    return full_name

# COMMAND ----------

# ------------------------------------------------------------
# setup_bronze_schema
# ------------------------------------------------------------
def setup_bronze_schema(catalog: str, schema: str) -> None:
    """
    Creates the Unity Catalog catalog and schema if they do not exist.
    Idempotent -- safe to call on every run.

    Why CREATE CATALOG and CREATE SCHEMA:
        External tables still require a Unity Catalog namespace to
        register under. The storage is decoupled from the catalog
        entry, but the entry itself must exist before CREATE TABLE.
    """
    spark.sql(f"CREATE CATALOG IF NOT EXISTS `{catalog}`")
    spark.sql(f"USE CATALOG `{catalog}`")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{schema}`")
    print(f"[SUCCESS] Ensured catalog '{catalog}' and schema '{schema}' exist")

# COMMAND ----------

# ------------------------------------------------------------
# append_etl_metadata
# ------------------------------------------------------------
def append_etl_metadata(df: DataFrame, etl_meta: Dict[str, str]) -> DataFrame:
    """
    Appends 7 ETL metadata columns to a DataFrame read by Autoloader.

    Architecture-required columns (Section 7.3):
      _ingested_at   -- TIMESTAMP, when Autoloader wrote this row to Bronze
      _source_file   -- STRING, S3 Parquet file path this row came from
      _ingest_date   -- STRING, partition-friendly date (YYYY-MM-DD)
      _row_hash      -- STRING, MD5 of all source columns for dedup reference

    Audit columns (production best practice):
      _job_run_id    -- STRING, <jobId>_<runId> ties batch to Databricks Job log
      _notebook_path -- STRING, which Bronze notebook produced this row
      _source_system -- STRING, constant "NYC_OPEN_DATA"

    CRITICAL: _row_hash is computed BEFORE adding any metadata columns.
    This ensures the hash reflects only source API columns and remains
    stable across re-ingestions. If metadata columns were included,
    the hash would change on every run even for identical source data,
    defeating its purpose as a downstream dedup reference.

    _source_file uses _metadata.file_path (the Autoloader-native hidden
    column) instead of input_file_name(). _metadata is the recommended
    API for cloudFiles -- it provides richer context and is more
    reliable in streaming mode. We extract only the field we need
    rather than selecting the full _metadata struct, which prevents
    schema evolution issues if Databricks updates the hidden struct
    in future runtime versions.

    Note: _metadata is a hidden column. It does not appear in
    df.columns and is not written to the Delta table unless
    explicitly referenced. No .drop("_metadata") is needed.
    """
    # Step 1: Compute _row_hash on source columns ONLY
    # df.columns returns only visible columns -- _metadata is excluded
    source_columns = df.columns
    df_with_hash = df.withColumn(
        "_row_hash",
        F.md5(F.to_json(F.struct(*[F.col(c) for c in source_columns])))
    )

    # Step 2: Add architecture-required metadata
    df_with_meta = (
        df_with_hash
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_ingest_date", F.date_format(F.current_date(), "yyyy-MM-dd"))
    )

    # Step 3: Add audit metadata
    df_final = (
        df_with_meta
        .withColumn("_job_run_id",    F.lit(etl_meta["job_run_id"]))
        .withColumn("_notebook_path", F.lit(etl_meta["notebook_path"]))
        .withColumn("_source_system", F.lit(etl_meta["source_system"]))
    )

    return df_final

# COMMAND ----------

# ------------------------------------------------------------
# _read_streaming_metrics  (internal helper)
# ------------------------------------------------------------
def _read_streaming_metrics(query) -> int:
    """
    Reads total rows written from the streaming query progress.

    After trigger(availableNow=True) completes and awaitTermination()
    returns, query.recentProgress contains the progress of all
    micro-batches processed during the run. Each entry has
    numInputRows -- the rows read per micro-batch. Since Bronze is
    append-only with no row filtering, numInputRows == rows written.

    This is a pure in-memory read from the driver -- no Delta log
    access, no data scan. The metrics are the write receipt.

    Returns:
        Total rows written as int, or -1 if metrics unavailable.
        -1 is non-blocking -- callers log a warning and continue.
    """
    try:
        rows_written = 0
        for progress in query.recentProgress:
            rows_written += progress.numInputRows
        print(f"[INFO] Records committed (streaming metrics): {rows_written:,}")
        return rows_written
    except Exception as e:
        print(f"[WARN] Could not read streaming metrics: {e}")
        return -1

# COMMAND ----------

# ------------------------------------------------------------
# load_bronze_autoloader
# ------------------------------------------------------------
def load_bronze_autoloader(
    source_path:     str,
    checkpoint_path: str,
    delta_location:  str,
    etl_meta:        Dict[str, str],
    table_name:      str = "",
) -> int:
    """
    Core Autoloader function. Reads Parquet files from S3 using
    cloudFiles format, appends ETL metadata, and writes to Delta.

    Architecture principles enforced:
      - Pure append INSERT -- no MERGE at Bronze layer
      - All source columns retained -- no column dropping
      - Checkpoint-based file tracking prevents re-ingestion
      - Deduplication delegated to dbt Staging

    Write strategy: writeStream + trigger(availableNow=True)
      - Starts the stream, processes all currently available files,
        then auto-terminates. No always-on cluster cost.
      - Checkpoint tracks which files have been processed. Files
        already tracked are never re-read, even across job runs.
      - If no new files are detected, the stream terminates with
        0 rows processed -- this is a valid outcome, not an error.

    Why .start(delta_location) instead of .toTable():
      - .toTable() creates a managed table. We need external tables
        with user-specified S3 storage locations.
      - .start(path) writes Delta files to the specified S3 path.
      - The table is registered separately via register_table().
      - Storage and catalog metadata are intentionally decoupled.

    Schema handling:
      - cloudFiles.schemaLocation stores the inferred schema at the
        checkpoint path. Standard Databricks pattern.
      - cloudFiles.inferColumnTypes lets Autoloader infer types from
        the Parquet file schema (our DAG casts all columns to string,
        so all source columns arrive as STRING in Bronze).
      - cloudFiles.schemaEvolutionMode = addNewColumns: if the
        Socrata API adds a new column, the next run after a single
        schema-update failure will pick it up automatically.
      - mergeSchema = true on the write side accepts new columns
        into the Delta table without manual ALTER TABLE.

    Parameters
    ----------
    source_path : str
        S3 path where raw Parquet files are stored.
    checkpoint_path : str
        S3 path for Autoloader checkpoint and schema location.
    delta_location : str
        S3 path where Delta table files are written.
    etl_meta : dict
        ETL metadata from resolve_etl_metadata().
    table_name : str
        Table name for logging only.

    Returns
    -------
    int
        Total rows written. 0 if no new files. -1 if metrics unavailable.
    """
    print(f"[START] Autoloader ingestion: {table_name}")
    print(f"  Source     : {source_path}")
    print(f"  Delta      : {delta_location}")
    print(f"  Checkpoint : {checkpoint_path}")

    try:
        # Read from S3 using Autoloader
        raw_df = (
            spark.readStream
            .format("cloudFiles")
            .option("cloudFiles.format", "parquet")
            .option("cloudFiles.schemaLocation", checkpoint_path)
            .option("cloudFiles.inferColumnTypes", "true")
            .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
            .load(source_path)
        )

        # Add ETL metadata columns
        bronze_df = append_etl_metadata(raw_df, etl_meta)

        # Write to Delta -- append-only, batch trigger
        query = (
            bronze_df.writeStream
            .format("delta")
            .outputMode("append")
            .option("checkpointLocation", checkpoint_path)
            .option("mergeSchema", "true")
            .trigger(availableNow=True)
            .start(delta_location)
        )

        # Block until all available files are processed
        query.awaitTermination()

        # Read metrics from completed streaming query
        rows_written = _read_streaming_metrics(query)

        if rows_written == 0:
            print(f"[INFO] No new files detected for {table_name} -- 0 rows written")
        else:
            print(f"[SUCCESS] Autoloader ingestion complete: {table_name}")

        return rows_written

    except Exception as e:
        raise RuntimeError(
            f"FAILED: Autoloader ingestion failed for '{table_name}'. Error: {e}"
        )

# COMMAND ----------

# ------------------------------------------------------------
# register_table
# ------------------------------------------------------------
def register_table(full_table_name: str, s3_target_path: str) -> None:
    """
    Registers the Delta table in Unity Catalog as an external table.
    CREATE TABLE IF NOT EXISTS is a no-op on subsequent runs --
    safe to call on every execution.

    Storage and metadata are intentionally decoupled:
    Delta files exist on S3 independently of the catalog entry.
    Dropping the catalog entry does not delete data.
    Re-registering points the catalog back at existing data.
    """
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {full_table_name}
        USING DELTA
        LOCATION '{s3_target_path}'
    """)
    print(f"[SUCCESS] Table registered: {full_table_name}")

# COMMAND ----------

# ------------------------------------------------------------
# post_write_validation_bronze
# ------------------------------------------------------------
def post_write_validation_bronze(
    full_table_name: str,
    rows_written:    int,
    job_run_id:      str = None,
) -> None:
    """
    Validates the registered Bronze table after write.

    What this checks:
      1. rows_written > 0 -- zero records means no data was committed.
         This is a hard failure because this function is only called
         when the caller confirmed rows_written > 0. If we still see
         zero here, something is wrong.
      2. All 7 ETL metadata columns are present and non-NULL in the
         current batch (filtered by _job_run_id when provided).
         NULL metadata means context resolution or append_etl_metadata
         logic silently failed, which must be caught before Silver runs.
    """
    print("[START] Post-write validation")
    print(f"[INFO]  Rows written (streaming metrics): {rows_written:,}")
    if job_run_id:
        print(f"[INFO]  Validating batch for _job_run_id: {job_run_id}")

    try:
        if rows_written == 0:
            raise ValueError(
                "FAILED: Zero records committed. "
                "Aborting to prevent silent empty-table propagation."
            )

        df_val = spark.table(full_table_name)
        if job_run_id:
            df_val = df_val.filter(F.col("_job_run_id") == job_run_id)
            batch_count = df_val.count()
            if batch_count == 0:
                raise ValueError(
                    f"FAILED: No rows found for _job_run_id '{job_run_id}' "
                    "despite positive streaming metrics."
                )
            print(f"[INFO]  Batch row count in table: {batch_count:,}")

        # All 7 ETL metadata columns
        meta_cols = [
            "_ingested_at",
            "_source_file",
            "_ingest_date",
            "_row_hash",
            "_job_run_id",
            "_notebook_path",
            "_source_system",
        ]

        # Verify columns exist
        missing = [c for c in meta_cols if c not in df_val.columns]
        if missing:
            raise ValueError(
                f"FAILED: Missing ETL metadata columns: {missing}. "
                f"Available columns: {df_val.columns}"
            )

        # Single-pass aggregation — all NULL checks in one Spark action
        null_counts = df_val.select([
            F.count(F.when(F.col(c).isNull(), 1)).alias(c)
            for c in meta_cols
        ]).collect()[0]

        failed = []
        for col_name in meta_cols:
            null_count = null_counts[col_name]
            status     = "[PASS]" if null_count == 0 else "[FAIL]"
            if null_count > 0:
                failed.append(col_name)
            print(f"  {status} {col_name}: {null_count:,} NULLs")

        if failed:
            raise ValueError(
                f"FAILED: NULL values in ETL metadata columns {failed}. "
                "Check context resolution and append_etl_metadata logic."
            )

        print("[SUCCESS] Post-write validation passed")

    except Exception as e:
        raise RuntimeError(f"Post-write validation failed: {e}")

# COMMAND ----------

# ------------------------------------------------------------
# print_summary
# ------------------------------------------------------------
def print_summary(
    label:           str,
    full_table_name: str,
    s3_source_path:  str,
    s3_target_path:  str,
    etl_meta:        Dict[str, str],
    extra_info:      Dict[str, Any] = None
) -> None:
    """
    Prints a standardized run summary for Bronze notebooks.
    extra_info accepts loader-specific metrics (rows written, etc.).
    """
    print("\n" + "=" * 70)
    print(f"BRONZE {label.upper()} INGESTION SUMMARY")
    print("=" * 70)
    print(f"Table          : {full_table_name}")
    print(f"Source         : {s3_source_path}")
    print(f"Target (Delta) : {s3_target_path}")
    print(f"\nETL Metadata")
    print(f"  _job_run_id    : {etl_meta['job_run_id']}")
    print(f"  _notebook_path : {etl_meta['notebook_path']}")
    print(f"  _source_system : {etl_meta['source_system']}")

    if extra_info:
        print(f"\nRun Details")
        for key, val in extra_info.items():
            print(f"  {key:<26}: {val}")

    print("=" * 70)
    print(f"[END] Bronze {label} ingestion completed successfully")
    print("=" * 70)

# COMMAND ----------

print("[INFO] bronze_utils loaded successfully")

