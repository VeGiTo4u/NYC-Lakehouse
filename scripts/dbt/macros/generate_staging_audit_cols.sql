{#
    generate_staging_audit_cols()
    
    Produces a consistent set of audit & metadata columns for all staging models.
    Call this macro at the end of your SELECT list (after a trailing comma).

    Columns carried from Bronze (per NYC_Dataset_Analysis §8):
      - _row_hash        MD5 of source row — used by dedup window function
      - _ingested_at     Autoloader write timestamp — incremental predicate key
      - _source_file     S3 Parquet file path — audit trail
      - _ingest_date     Partition date — partition pruning

    New staging-level audit columns:
      - _stg_loaded_at   Timestamp when staging processed this row
      - _stg_model_name  Name of the dbt model that produced this row
      - _stg_run_id      dbt invocation ID for run-level traceability

    Usage:
      SELECT
          col_a,
          col_b,
          {{ generate_staging_audit_cols() }}
      FROM ...
#}

{% macro generate_staging_audit_cols() %}
    -- ── Bronze ETL metadata (carried forward) ──
    _row_hash,
    _ingested_at,
    _source_file,
    _ingest_date,

    -- ── Staging audit columns (added at this layer) ──
    CURRENT_TIMESTAMP()       AS _stg_loaded_at,
    '{{ this.name }}'         AS _stg_model_name,
    '{{ invocation_id }}'     AS _stg_run_id
{% endmacro %}
