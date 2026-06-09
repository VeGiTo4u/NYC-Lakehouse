{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['zip_code', 'year_month'],
        location_root='s3://nyc-lakehouse-store/silver/intermediate'
    )
-}}

{#
    int_permits_by_zip_month

    Aggregates staged DOB permit records to zip_code + year_month grain.
    Produces per-zip, per-month permit issuance counts and activity metrics.

    Grain:     zip_code + year_month (one row per zip per month)
    Unique key: [zip_code, year_month]
    Strategy:  Incremental MERGE with 90-day lookback (var: lookback_days_default)
    Source:    stg_dob_permits

    References:
      - High-Level Architecture §7.5 (int_permits_by_zip_month)
      - High-Level Architecture §10 (Incremental Strategy — 90-day default)
      - CLAUDE.md §4 (Late-Arriving Data — MERGE with lookback)
#}

WITH source AS (

    SELECT
        zip_code,
        year_month,
        job_type,
        is_active_permit
    FROM {{ ref('stg_dob_permits') }}
    WHERE zip_code IS NOT NULL
      AND year_month IS NOT NULL
    {% if is_incremental() %}
      AND year_month >= DATE_FORMAT(
          DATE_SUB(CURRENT_DATE(), {{ var('lookback_days_default') }}),
          'yyyy-MM'
      )
    {% endif %}

),

aggregated AS (

    SELECT
        zip_code,
        year_month,

        -- ── Volume metrics ──
        COUNT(*)                                                        AS total_permits_issued,

        -- ── Activity metrics ──
        SUM(is_active_permit)                                           AS active_permits,

        -- ── Job type breakdown ──
        COUNT(CASE WHEN job_type = 'NB' THEN 1 END)                   AS new_building_count,
        COUNT(CASE WHEN job_type IN ('A1', 'A2', 'A3') THEN 1 END)    AS alteration_count,
        COUNT(CASE WHEN job_type = 'DM' THEN 1 END)                   AS demolition_count

    FROM source
    GROUP BY zip_code, year_month

)

SELECT * FROM aggregated
