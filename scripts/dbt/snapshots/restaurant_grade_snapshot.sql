{% snapshot restaurant_grade_snapshot %}

{{
    config(
        target_schema='gold',
        unique_key='restaurant_id',
        strategy='check',
        check_cols=['inspection_grade', 'cuisine_type', 'restaurant_name', 'borough', 'zip_code'],
        invalidate_hard_deletes=True
    )
}}

{#
    restaurant_grade_snapshot

    SCD Type 2 snapshot tracking changes to restaurant attributes
    (grade, cuisine, name, location) over time.

    Uses dbt's check strategy — on each snapshot run, compares the
    current row's check_cols against the prior record. When a change
    is detected:
      - Sets dbt_valid_to on the old record to CURRENT_TIMESTAMP
      - Inserts a new record with dbt_valid_from = CURRENT_TIMESTAMP
        and dbt_valid_to = NULL

    This enables historical queries like:
      "How many restaurants that were grade C in Jan 2023 improved
       to grade A by Jan 2024?"

    Source: Latest record per restaurant from stg_restaurant_inspections
    Unique key: restaurant_id (= camis)
    Schema: gold

    IMPORTANT: Never full-refresh this model — SCD2 history is cumulative.

    References:
      - High-Level Architecture §7.7 (Snapshot — SCD Type 2)
      - High-Level Architecture §11 (SCD Type 2 scope — dim_restaurant only)
#}

-- Get the latest inspection record per restaurant
-- (most recent inspection_date, then most recent grade_assigned_date)
SELECT
    restaurant_id,
    restaurant_name,
    cuisine_type,
    borough,
    zip_code,
    inspection_grade,
    inspection_score,
    grade_assigned_date,
    inspection_date
FROM {{ ref('stg_restaurant_inspections') }}
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY restaurant_id
    ORDER BY inspection_date DESC, grade_assigned_date DESC NULLS LAST
) = 1

{% endsnapshot %}
