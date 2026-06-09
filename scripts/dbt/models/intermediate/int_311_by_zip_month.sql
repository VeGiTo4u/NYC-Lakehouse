{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['zip_code', 'year_month'],
        location_root='s3://nyc-lakehouse-store/silver/intermediate'
    )
-}}

{#
    int_311_by_zip_month

    Aggregates staged 311 service requests to zip_code + year_month grain.
    Produces per-zip, per-month complaint counts and resolution metrics
    ready for Gold layer consumption.

    Grain:     zip_code + year_month (one row per zip per month)
    Unique key: [zip_code, year_month]
    Strategy:  Incremental MERGE with 90-day lookback (var: lookback_days_default)
    Source:    stg_311_requests

    References:
      - High-Level Architecture §7.5 (int_311_by_zip_month)
      - High-Level Architecture §10 (Incremental Strategy — 90-day default)
      - CLAUDE.md §4 (Late-Arriving Data — MERGE with lookback)
#}

WITH source AS (

    SELECT
        zip_code,
        year_month,
        complaint_type,
        complaint_status,
        resolution_time_hours
    FROM {{ ref('stg_311_requests') }}
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
        COUNT(*)                                                        AS total_complaints,

        -- ── Complaint type breakdowns (conditional counts) ──
        COUNT(CASE WHEN complaint_type LIKE '%Noise%' THEN 1 END)      AS noise_complaints,
        COUNT(CASE WHEN complaint_type LIKE '%Food%' THEN 1 END)       AS food_complaints,
        COUNT(CASE
            WHEN complaint_type LIKE '%Construction%'
              OR complaint_type LIKE '%Building%'
            THEN 1
        END)                                                            AS construction_complaints,

        -- ── Resolution metrics ──
        ROUND(AVG(resolution_time_hours), 2)                            AS avg_resolution_hours,

        -- ── Status breakdown ──
        COUNT(CASE WHEN complaint_status = 'Open' THEN 1 END)          AS open_complaints,
        COUNT(CASE WHEN complaint_status = 'Closed' THEN 1 END)        AS closed_complaints

    FROM source
    GROUP BY zip_code, year_month

)

SELECT * FROM aggregated
