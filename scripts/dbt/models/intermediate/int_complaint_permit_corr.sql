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

    Cross-domain join linking construction permit activity to 311 complaint
    volumes at zip_code + year_month grain. Feeds mart_safety_infrastructure_corr
    and underpins analytical question Q16:
      "Does construction activity predict a rise in noise complaints 1–2 months later?"

    Both source models are already at zip+month grain — this is a JOIN, not an
    aggregation. No GROUP BY needed. All aggregation happened in the source models.

    Grain:     zip_code + year_month (one row per zip per month)
    Unique key: [zip_code, year_month]
    Strategy:  Incremental MERGE with 90-day lookback (same cadence as source models)
    Sources:   int_311_by_zip_month + int_permits_by_zip_month

    References:
      - High-Level Architecture §7.5 (int_complaint_permit_corr)
      - High-Level Architecture §2 Q16 (cross-domain analytical question)
      - High-Level Architecture §5.4 (311 ↔ DOB join on zip + month)
#}

WITH complaints AS (

    SELECT
        zip_code,
        year_month,
        noise_complaints,
        construction_complaints,
        total_complaints
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

joined AS (

    SELECT
        -- ── Grain keys ──
        c.zip_code,
        c.year_month,

        -- ── 311 complaint signals ──
        c.noise_complaints,
        c.construction_complaints,
        c.total_complaints,

        -- ── DOB permit signals ──
        COALESCE(p.total_permits_issued, 0)     AS total_permits_issued,
        COALESCE(p.active_permits, 0)           AS active_permits,
        COALESCE(p.new_building_count, 0)       AS new_building_count

    FROM complaints c
    LEFT JOIN permits p
        ON c.zip_code   = p.zip_code
       AND c.year_month = p.year_month

)

SELECT * FROM joined
