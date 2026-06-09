{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['zip_code', 'year_month'],
        location_root='s3://nyc-lakehouse-store/silver/intermediate'
    )
-}}

{#
    int_complaint_permit_corr

    Cross-domain join model: 311 complaints × DOB permits at zip_code + year_month.
    Enables correlation analysis between construction/permit activity and
    complaint volumes (especially noise and construction complaints).

    Uses FULL OUTER JOIN to preserve zip codes that appear in only one
    source — a zip code with permits but zero complaints (or vice versa)
    should still appear in the output.

    Grain:     zip_code + year_month (one row per zip per month)
    Unique key: [zip_code, year_month]
    Strategy:  Incremental MERGE with 90-day lookback (var: lookback_days_default)
    Sources:   int_311_by_zip_month + int_permits_by_zip_month

    References:
      - High-Level Architecture §7.5 (int_complaint_permit_corr)
      - Analytical Questions Q16: Does construction activity predict noise complaints?
#}

WITH complaints AS (

    SELECT
        zip_code,
        year_month,
        total_complaints,
        noise_complaints,
        construction_complaints,
        avg_resolution_hours
    FROM {{ ref('int_311_by_zip_month') }}
    {% if is_incremental() %}
    WHERE year_month >= DATE_FORMAT(
        DATE_SUB(CURRENT_DATE(), {{ var('lookback_days_default') }}),
        'yyyy-MM'
    )
    {% endif %}

),

permits AS (

    SELECT
        zip_code,
        year_month,
        total_permits_issued,
        active_permits,
        new_building_count
    FROM {{ ref('int_permits_by_zip_month') }}
    {% if is_incremental() %}
    WHERE year_month >= DATE_FORMAT(
        DATE_SUB(CURRENT_DATE(), {{ var('lookback_days_default') }}),
        'yyyy-MM'
    )
    {% endif %}

),

-- FULL OUTER JOIN ensures zip codes appearing in only one dataset are retained
joined AS (

    SELECT
        COALESCE(c.zip_code, p.zip_code)                                AS zip_code,
        COALESCE(c.year_month, p.year_month)                            AS year_month,

        -- ── Complaint metrics (NULL when zip has no complaints that month) ──
        c.total_complaints,
        c.noise_complaints,
        c.construction_complaints,
        c.avg_resolution_hours,

        -- ── Permit metrics (NULL when zip has no permits that month) ──
        p.total_permits_issued,
        p.active_permits,
        p.new_building_count

    FROM complaints c
    FULL OUTER JOIN permits p
        ON c.zip_code = p.zip_code
       AND c.year_month = p.year_month

)

SELECT * FROM joined
