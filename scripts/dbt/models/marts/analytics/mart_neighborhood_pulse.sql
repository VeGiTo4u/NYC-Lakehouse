{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['zip_code', 'year_month'],
        schema='gold'
    )
-}}

{#
    mart_neighborhood_pulse

    Denormalized, Streamlit-ready wide table joining the fact table
    with all dimension tables. Zero-join convenience for the dashboard —
    all dimension attributes are flattened into each row.

    This is the primary data source for the Neighborhood Explorer page
    in Streamlit. Consumers read a single table instead of joining
    fct + dims at query time.

    Grain:     zip_code + year_month (same as fact table)
    Unique key: [zip_code, year_month]
    Strategy:  Incremental MERGE with 90-day lookback
    Sources:   fact_neighborhood_monthly + dim_zip_codes + dim_date
    Schema:    gold
    Target:    nyc-lakehouse.gold.mart_neighborhood_pulse

    References:
      - High-Level Architecture §7.6 (mart_neighborhood_pulse)
      - High-Level Architecture §7.8 (Streamlit — Neighborhood Explorer page)
#}

WITH fact AS (

    SELECT *
    FROM {{ ref('fact_neighborhood_monthly') }}
    {% if is_incremental() %}
    WHERE year_month >= DATE_FORMAT(
        DATE_SUB(CURRENT_DATE(), {{ var('lookback_days_default') }}),
        'yyyy-MM'
    )
    {% endif %}

),

dim_zip AS (

    SELECT
        zip_code,
        borough,
        neighborhood_name,
        nta_code
    FROM {{ ref('dim_zip_codes') }}

),

dim_dt AS (

    SELECT
        year_month,
        year,
        month,
        quarter,
        month_name,
        is_current_month,
        is_complete_month
    FROM {{ ref('dim_date') }}

)

SELECT
    -- ── Grain keys ──
    f.zip_code,
    f.year_month,

    -- ── Zip dimension attributes ──
    z.borough,
    z.neighborhood_name,
    z.nta_code,

    -- ── Date dimension attributes ──
    d.year,
    d.month,
    d.quarter,
    d.month_name,
    d.is_current_month,
    d.is_complete_month,

    -- ── 311 Complaint measures ──
    f.total_complaints,
    f.noise_complaint_count,
    f.food_complaint_count,
    f.construction_complaint_count,
    f.avg_resolution_hours,
    f.open_complaint_count,
    f.closed_complaint_count,

    -- ── NYPD Arrest measures ──
    f.total_arrests,
    f.felony_count,
    f.misdemeanor_count,
    f.violation_count,

    -- ── DOB Permit measures ──
    f.total_permits_issued,
    f.active_permit_count,
    f.new_building_count,
    f.alteration_count,
    f.demolition_count,

    -- ── Restaurant Inspection measures ──
    f.total_inspections,
    f.unique_restaurants_inspected,
    f.avg_inspection_score,
    f.pct_grade_a,
    f.pct_grade_b,
    f.pct_grade_c,
    f.critical_violation_count,

    -- ── Composite KPI ──
    f.neighborhood_pulse_score,

    -- ── Audit columns ──
    {{ generate_gold_audit_cols() }}

FROM fact f

LEFT JOIN dim_zip z
    ON f.zip_code = z.zip_code

LEFT JOIN dim_dt d
    ON f.year_month = d.year_month
