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
    mart_safety_infrastructure_corr

    Arrests × permits correlation mart — combines NYPD arrest data with
    DOB permit data at the zip_code + year_month grain for correlation
    and trend analysis.

    Uses FULL OUTER JOIN to preserve zip codes appearing in only one
    dataset — a zip code with arrests but zero permits (or vice versa)
    still appears in the output.

    Grain:     zip_code + year_month
    Unique key: [zip_code, year_month]
    Strategy:  Incremental MERGE with lookback
    Sources:   int_arrests_by_zip_month + int_permits_by_zip_month
    Schema:    gold
    Target:    nyc-lakehouse.gold.mart_safety_infrastructure_corr

    References:
      - High-Level Architecture §7.6 (mart_safety_infrastructure_corr)
      - High-Level Architecture §7.8 (Streamlit — Safety × Infrastructure page)
#}

WITH arrests AS (

    SELECT
        zip_code,
        year_month,
        total_arrests,
        felony_count,
        misdemeanor_count,
        violation_count
    FROM {{ ref('int_arrests_by_zip_month') }}
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
        new_building_count,
        alteration_count,
        demolition_count
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
        COALESCE(a.zip_code, p.zip_code)                            AS zip_code,
        COALESCE(a.year_month, p.year_month)                        AS year_month,

        -- ── Arrest measures ──
        COALESCE(a.total_arrests, 0)                                AS total_arrests,
        COALESCE(a.felony_count, 0)                                 AS felony_count,
        COALESCE(a.misdemeanor_count, 0)                            AS misdemeanor_count,
        COALESCE(a.violation_count, 0)                              AS violation_count,

        -- ── Permit measures ──
        COALESCE(p.total_permits_issued, 0)                         AS total_permits_issued,
        COALESCE(p.active_permits, 0)                               AS active_permit_count,
        COALESCE(p.new_building_count, 0)                           AS new_building_count,
        COALESCE(p.alteration_count, 0)                             AS alteration_count,
        COALESCE(p.demolition_count, 0)                             AS demolition_count,

        -- ── Derived correlation measures ──
        {{ safe_divide(
            'COALESCE(a.total_arrests, 0)',
            'NULLIF(COALESCE(p.total_permits_issued, 0), 0)',
            2
        ) }}                                                        AS arrests_per_permit,

        {{ safe_divide(
            'COALESCE(a.felony_count, 0)',
            'NULLIF(COALESCE(a.total_arrests, 0), 0)',
            4
        ) }}                                                        AS felony_pct

    FROM arrests a
    FULL OUTER JOIN permits p
        ON a.zip_code = p.zip_code
       AND a.year_month = p.year_month

)

SELECT
    zip_code,
    year_month,
    total_arrests,
    felony_count,
    misdemeanor_count,
    violation_count,
    total_permits_issued,
    active_permit_count,
    new_building_count,
    alteration_count,
    demolition_count,
    arrests_per_permit,
    felony_pct,

    -- ── Audit columns ──
    {{ generate_gold_audit_cols() }}

FROM joined
