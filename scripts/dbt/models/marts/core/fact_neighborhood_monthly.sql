{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['zip_code', 'year_month'],
        schema='gold',
        location_root='s3://nyc-lakehouse-store/gold/core'
    )
-}}

{#
    fact_neighborhood_monthly

    Central fact table — one row per zip_code per year_month across all
    four data domains (311, NYPD, DOB, Restaurant Inspections).

    Uses zip_month_spine macro to generate a complete grid of all zip
    codes × all months, then LEFT JOINs each intermediate model to fill
    in measures. COALESCE wraps every measure to prevent NULL propagation
    into the neighborhood_pulse_score composite KPI.

    Grain:     zip_code + year_month (one row per zip per month)
    Unique key: [zip_code, year_month]
    Strategy:  Incremental MERGE with 90-day lookback
    Sources:   zip_month_spine + all 4 intermediate models + dim_zip_codes
    Schema:    gold
    Target:    nyc-lakehouse.gold.fact_neighborhood_monthly

    References:
      - High-Level Architecture §7.6 (fact_neighborhood_monthly)
      - High-Level Architecture §7.6 (Neighborhood Pulse Score Formula)
      - CLAUDE.md §5 (NULL Safety in KPIs)
      - High-Level Architecture §15 (Star Schema)
#}

WITH spine AS (

    -- Complete grid: every zip code × every month
    {{ zip_month_spine() }}

),

-- ═══════════════════════════════════════════════════════════════════
-- Filter spine to lookback window on incremental runs
-- ═══════════════════════════════════════════════════════════════════
filtered_spine AS (

    SELECT *
    FROM spine
    {% if is_incremental() %}
    WHERE year_month >= DATE_FORMAT(
        DATE_SUB(CURRENT_DATE(), {{ var('lookback_days_default') }}),
        'yyyy-MM'
    )
    {% endif %}

),

-- ═══════════════════════════════════════════════════════════════════
-- Source: 311 complaints by zip + month
-- ═══════════════════════════════════════════════════════════════════
complaints AS (

    SELECT
        zip_code,
        year_month,
        total_complaints,
        noise_complaints,
        food_complaints,
        construction_complaints,
        avg_resolution_hours,
        open_complaints,
        closed_complaints
    FROM {{ ref('int_311_by_zip_month') }}

),

-- ═══════════════════════════════════════════════════════════════════
-- Source: NYPD arrests by zip + month
-- ═══════════════════════════════════════════════════════════════════
arrests AS (

    SELECT
        zip_code,
        year_month,
        total_arrests,
        felony_count,
        misdemeanor_count,
        violation_count
    FROM {{ ref('int_arrests_by_zip_month') }}

),

-- ═══════════════════════════════════════════════════════════════════
-- Source: DOB permits by zip + month
-- ═══════════════════════════════════════════════════════════════════
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

),

-- ═══════════════════════════════════════════════════════════════════
-- Source: Restaurant inspections by zip + month
-- ═══════════════════════════════════════════════════════════════════
inspections AS (

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

),

-- ═══════════════════════════════════════════════════════════════════
-- Join all sources onto the spine
-- ═══════════════════════════════════════════════════════════════════
joined AS (

    SELECT
        -- ── Grain keys ──
        s.zip_code,
        s.year_month,

        -- ── Borough from dimension (FK) ──
        s.borough,

        -- ── 311 Complaint measures ──
        COALESCE(c.total_complaints, 0)                             AS total_complaints,
        COALESCE(c.noise_complaints, 0)                             AS noise_complaint_count,
        COALESCE(c.food_complaints, 0)                              AS food_complaint_count,
        COALESCE(c.construction_complaints, 0)                      AS construction_complaint_count,
        c.avg_resolution_hours,
        COALESCE(c.open_complaints, 0)                              AS open_complaint_count,
        COALESCE(c.closed_complaints, 0)                            AS closed_complaint_count,

        -- ── NYPD Arrest measures ──
        COALESCE(a.total_arrests, 0)                                AS total_arrests,
        COALESCE(a.felony_count, 0)                                 AS felony_count,
        COALESCE(a.misdemeanor_count, 0)                            AS misdemeanor_count,
        COALESCE(a.violation_count, 0)                              AS violation_count,

        -- ── DOB Permit measures ──
        COALESCE(p.total_permits_issued, 0)                         AS total_permits_issued,
        COALESCE(p.active_permits, 0)                               AS active_permit_count,
        COALESCE(p.new_building_count, 0)                           AS new_building_count,
        COALESCE(p.alteration_count, 0)                             AS alteration_count,
        COALESCE(p.demolition_count, 0)                             AS demolition_count,

        -- ── Restaurant Inspection measures ──
        COALESCE(i.total_inspections, 0)                            AS total_inspections,
        COALESCE(i.unique_restaurants_inspected, 0)                 AS unique_restaurants_inspected,
        i.avg_score                                                 AS avg_inspection_score,
        i.pct_grade_a,
        i.pct_grade_b,
        i.pct_grade_c,
        COALESCE(i.critical_violation_count, 0)                     AS critical_violation_count

    FROM filtered_spine s

    LEFT JOIN complaints c
        ON s.zip_code = c.zip_code
       AND s.year_month = c.year_month

    LEFT JOIN arrests a
        ON s.zip_code = a.zip_code
       AND s.year_month = a.year_month

    LEFT JOIN permits p
        ON s.zip_code = p.zip_code
       AND s.year_month = p.year_month

    LEFT JOIN inspections i
        ON s.zip_code = i.zip_code
       AND s.year_month = i.year_month

),

-- ═══════════════════════════════════════════════════════════════════
-- Compute neighborhood_pulse_score composite KPI
-- ═══════════════════════════════════════════════════════════════════
with_pulse_score AS (

    SELECT
        *,

        -- Neighborhood Pulse Score (0–100, higher = healthier)
        -- Formula from High-Level Architecture §7.6:
        --   complaint_factor  = (100 - LEAST(complaints/100, 100)) * 0.25
        --   arrest_factor     = (100 - LEAST(arrests/50, 100))     * 0.25
        --   permit_factor     = (100 - LEAST(active_permits/20, 100)) * 0.20
        --   food_safety       = (pct_grade_a * 100)                * 0.30
        ROUND(
            (100 - LEAST(COALESCE(total_complaints, 0) / 100.0, 100)) * 0.25
          + (100 - LEAST(COALESCE(total_arrests, 0) / 50.0, 100)) * 0.25
          + (100 - LEAST(COALESCE(active_permit_count, 0) / 20.0, 100)) * 0.20
          + (COALESCE(pct_grade_a, 0) * 100) * 0.30
        , 2)                                                        AS neighborhood_pulse_score

    FROM joined

)

SELECT
    -- ── Grain keys ──
    zip_code,
    year_month,

    -- ── Dimension FK ──
    borough,

    -- ── 311 Complaint measures ──
    total_complaints,
    noise_complaint_count,
    food_complaint_count,
    construction_complaint_count,
    avg_resolution_hours,
    open_complaint_count,
    closed_complaint_count,

    -- ── NYPD Arrest measures ──
    total_arrests,
    felony_count,
    misdemeanor_count,
    violation_count,

    -- ── DOB Permit measures ──
    total_permits_issued,
    active_permit_count,
    new_building_count,
    alteration_count,
    demolition_count,

    -- ── Restaurant Inspection measures ──
    total_inspections,
    unique_restaurants_inspected,
    avg_inspection_score,
    pct_grade_a,
    pct_grade_b,
    pct_grade_c,
    critical_violation_count,

    -- ── Composite KPI ──
    neighborhood_pulse_score,

    -- ── Audit columns ──
    {{ generate_gold_audit_cols() }}

FROM with_pulse_score
