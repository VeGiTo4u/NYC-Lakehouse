{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['zip_code', 'year_month'],
        location_root='s3://nyc-lakehouse-store/silver/intermediate'
    )
-}}

{#
    int_arrests_by_zip_month

    Aggregates staged NYPD arrest records to zip_code + year_month grain.
    Produces per-zip, per-month arrest counts broken down by severity level.

    NYPD-specific: Uses 200-day lookback (var: lookback_days_nypd) because
    the NYPD Historic dataset updates quarterly — a quarterly release can
    include corrections to records 3–6 months old.

    Excludes zip_code = 'UNKNOWN' (arrests with NULL coordinates that fell
    back to borough-level assignment) since these cannot be joined at
    the Gold layer by zip code.

    Grain:     zip_code + year_month (one row per zip per month)
    Unique key: [zip_code, year_month]
    Strategy:  Incremental MERGE with 200-day lookback (var: lookback_days_nypd)
    Source:    stg_nypd_arrests

    References:
      - High-Level Architecture §7.5 (int_arrests_by_zip_month)
      - High-Level Architecture §10 (Incremental Strategy — 200-day NYPD)
      - CLAUDE.md §4 (Late-Arriving Data — MERGE with lookback)
#}

WITH source AS (

    SELECT
        zip_code,
        year_month,
        law_category
    FROM {{ ref('stg_nypd_arrests') }}
    WHERE zip_code IS NOT NULL
      AND zip_code != 'UNKNOWN'
      AND year_month IS NOT NULL
    {% if is_incremental() %}
      AND year_month >= DATE_FORMAT(
          DATE_SUB(CURRENT_DATE(), {{ var('lookback_days_nypd') }}),
          'yyyy-MM'
      )
    {% endif %}

),

aggregated AS (

    SELECT
        zip_code,
        year_month,

        -- ── Volume metrics ──
        COUNT(*)                                                        AS total_arrests,

        -- ── Severity breakdown ──
        COUNT(CASE WHEN law_category = 'F' THEN 1 END)                AS felony_count,
        COUNT(CASE WHEN law_category = 'M' THEN 1 END)                AS misdemeanor_count,
        COUNT(CASE WHEN law_category = 'V' THEN 1 END)                AS violation_count

    FROM source
    GROUP BY zip_code, year_month

)

SELECT * FROM aggregated
