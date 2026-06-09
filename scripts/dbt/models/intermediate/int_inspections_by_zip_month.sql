{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['zip_code', 'year_month'],
        location_root='s3://nyc-lakehouse-store/silver/intermediate'
    )
-}}

{#
    int_inspections_by_zip_month

    Aggregates staged restaurant inspection records to zip_code + year_month grain.
    Produces per-zip, per-month inspection metrics including grade distribution.

    IMPORTANT — Dedup-aware aggregation:
      The staging table has one row per violation (grain: restaurant_id +
      inspection_date + violation_code + inspection_type). One inspection visit
      produces multiple violation rows, all sharing the same score and grade.

      To avoid inflated counts:
        - total_inspections, avg_score, grade percentages → computed at the
          INSPECTION VISIT level (deduplicated by restaurant_id + inspection_date)
        - critical_violation_count → computed at the VIOLATION ROW level
          (each critical violation should be counted)

    Grain:     zip_code + year_month (one row per zip per month)
    Unique key: [zip_code, year_month]
    Strategy:  Incremental MERGE with 90-day lookback (var: lookback_days_default)
    Source:    stg_restaurant_inspections

    References:
      - High-Level Architecture §7.5 (int_inspections_by_zip_month)
      - High-Level Architecture §10 (Incremental Strategy — 90-day default)
      - CLAUDE.md §4 (Late-Arriving Data — MERGE with lookback)
#}

WITH source AS (

    SELECT
        restaurant_id,
        inspection_date,
        violation_code,
        inspection_type,
        zip_code,
        year_month,
        inspection_score,
        inspection_grade,
        is_critical_violation
    FROM {{ ref('stg_restaurant_inspections') }}
    WHERE zip_code IS NOT NULL
      AND year_month IS NOT NULL
    {% if is_incremental() %}
      AND year_month >= DATE_FORMAT(
          DATE_SUB(CURRENT_DATE(), {{ var('lookback_days_default') }}),
          'yyyy-MM'
      )
    {% endif %}

),

-- ═══════════════════════════════════════════════════════════════════
-- Step 1: Deduplicate to inspection-visit level
-- One row per (restaurant_id + inspection_date) — picks the first row
-- by violation_code to get the score/grade (which are identical across
-- all violation rows for the same visit).
-- ═══════════════════════════════════════════════════════════════════
inspection_visits AS (

    SELECT
        restaurant_id,
        inspection_date,
        zip_code,
        year_month,
        inspection_score,
        inspection_grade
    FROM source
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY restaurant_id, inspection_date
        ORDER BY violation_code, inspection_type
    ) = 1

),

-- ═══════════════════════════════════════════════════════════════════
-- Step 2: Visit-level aggregation (scores, grades, inspection counts)
-- ═══════════════════════════════════════════════════════════════════
visit_aggs AS (

    SELECT
        zip_code,
        year_month,

        -- Inspection volume
        COUNT(*)                                                        AS total_inspections,
        COUNT(DISTINCT restaurant_id)                                   AS unique_restaurants_inspected,

        -- Score metrics
        ROUND(AVG(inspection_score), 2)                                 AS avg_score,

        -- Grade distribution (only among graded inspections)
        ROUND(
            COUNT(CASE WHEN inspection_grade = 'A' THEN 1 END)
            * 1.0
            / NULLIF(COUNT(inspection_grade), 0),
        4)                                                              AS pct_grade_a,

        ROUND(
            COUNT(CASE WHEN inspection_grade = 'B' THEN 1 END)
            * 1.0
            / NULLIF(COUNT(inspection_grade), 0),
        4)                                                              AS pct_grade_b,

        ROUND(
            COUNT(CASE WHEN inspection_grade = 'C' THEN 1 END)
            * 1.0
            / NULLIF(COUNT(inspection_grade), 0),
        4)                                                              AS pct_grade_c

    FROM inspection_visits
    GROUP BY zip_code, year_month

),

-- ═══════════════════════════════════════════════════════════════════
-- Step 3: Violation-level aggregation (critical violations)
-- Counted at the raw violation row level — each critical violation
-- is a distinct regulatory event.
-- ═══════════════════════════════════════════════════════════════════
violation_aggs AS (

    SELECT
        zip_code,
        year_month,
        COUNT(CASE WHEN is_critical_violation = 'Critical' THEN 1 END) AS critical_violation_count

    FROM source
    GROUP BY zip_code, year_month

),

-- ═══════════════════════════════════════════════════════════════════
-- Step 4: Join visit-level and violation-level metrics
-- ═══════════════════════════════════════════════════════════════════
final AS (

    SELECT
        v.zip_code,
        v.year_month,
        v.total_inspections,
        v.unique_restaurants_inspected,
        v.avg_score,
        v.pct_grade_a,
        v.pct_grade_b,
        v.pct_grade_c,
        viol.critical_violation_count

    FROM visit_aggs v
    INNER JOIN violation_aggs viol
        ON v.zip_code = viol.zip_code
       AND v.year_month = viol.year_month

)

SELECT * FROM final
