{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['zip_code', 'year_month'],
        schema='gold',
        location_root='s3://nyc-lakehouse-store/gold/analytics'
    )
-}}

{#
    mart_food_compliance

    Food safety compliance mart — joins restaurant inspection metrics
    with 311 food complaints side by side at zip_code + year_month grain.

    Enables analysis of the overlap between DOHMH inspection outcomes
    and community-reported food complaints. FULL OUTER JOIN ensures
    zip codes with inspections but no food complaints (and vice versa)
    are preserved.

    Grain:     zip_code + year_month
    Unique key: [zip_code, year_month]
    Strategy:  Incremental MERGE with 90-day lookback
    Sources:   int_inspections_by_zip_month + int_311_by_zip_month
    Schema:    gold
    Target:    nyc-lakehouse.gold.mart_food_compliance

    References:
      - High-Level Architecture §7.6 (mart_food_compliance)
      - High-Level Architecture §7.8 (Streamlit — Food Safety Compliance page)
#}

WITH inspections AS (

    SELECT
        zip_code,
        year_month,
        total_inspections,
        unique_restaurants_inspected,
        avg_score,
        pct_grade_a,
        pct_grade_b,
        pct_grade_c,
        critical_violation_count
    FROM {{ ref('int_inspections_by_zip_month') }}
    {% if is_incremental() %}
    WHERE year_month >= DATE_FORMAT(
        DATE_SUB(CURRENT_DATE(), {{ var('lookback_days_default') }}),
        'yyyy-MM'
    )
    {% endif %}

),

food_complaints AS (

    SELECT
        zip_code,
        year_month,
        food_complaints  AS food_complaint_count
    FROM {{ ref('int_311_by_zip_month') }}
    {% if is_incremental() %}
    WHERE year_month >= DATE_FORMAT(
        DATE_SUB(CURRENT_DATE(), {{ var('lookback_days_default') }}),
        'yyyy-MM'
    )
    {% endif %}

),

joined AS (

    SELECT
        -- ── Grain keys ──
        COALESCE(i.zip_code, fc.zip_code)                           AS zip_code,
        COALESCE(i.year_month, fc.year_month)                       AS year_month,

        -- ── Restaurant inspection measures ──
        COALESCE(i.total_inspections, 0)                            AS total_inspections,
        COALESCE(i.unique_restaurants_inspected, 0)                 AS unique_restaurants_inspected,
        i.avg_score                                                 AS avg_inspection_score,
        i.pct_grade_a,
        i.pct_grade_b,
        i.pct_grade_c,
        COALESCE(i.critical_violation_count, 0)                     AS critical_violation_count,

        -- ── 311 food complaint measures ──
        COALESCE(fc.food_complaint_count, 0)                        AS food_complaint_count,

        -- ── Derived: food complaints per inspection ──
        {{ safe_divide(
            'COALESCE(fc.food_complaint_count, 0)',
            'NULLIF(COALESCE(i.total_inspections, 0), 0)',
            4
        ) }}                                                        AS food_complaints_per_inspection

    FROM inspections i
    FULL OUTER JOIN food_complaints fc
        ON i.zip_code = fc.zip_code
       AND i.year_month = fc.year_month

)

SELECT
    zip_code,
    year_month,
    total_inspections,
    unique_restaurants_inspected,
    avg_inspection_score,
    pct_grade_a,
    pct_grade_b,
    pct_grade_c,
    critical_violation_count,
    food_complaint_count,
    food_complaints_per_inspection,

    -- ── Audit columns ──
    {{ generate_gold_audit_cols() }}

FROM joined
