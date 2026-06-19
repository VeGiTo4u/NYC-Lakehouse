{#
    generate_gold_audit_cols()

    Produces a consistent set of audit columns for all Gold layer models.
    Call this macro at the end of your SELECT list (after a trailing comma).

    Mirrors the staging pattern (generate_staging_audit_cols) but scoped
    to the Gold layer with a _gold_ prefix.

    Columns:
      - _gold_loaded_at   Timestamp when Gold layer processed this row
      - _gold_model_name  Name of the dbt model that produced this row
      - _gold_run_id      dbt invocation ID for run-level traceability

    Usage:
      SELECT
          col_a,
          col_b,
          {{ generate_gold_audit_cols() }}
      FROM ...
#}

{% macro generate_gold_audit_cols() %}
    CURRENT_TIMESTAMP()       AS _gold_loaded_at,
    '{{ this.name }}'         AS _gold_model_name,
    '{{ invocation_id }}'     AS _gold_run_id
{% endmacro %}
