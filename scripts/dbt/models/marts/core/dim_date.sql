{{-
    config(
        materialized='table',
        schema='gold'
    )
-}}

{#
    dim_date

    Date dimension — month-grain spine from 2006-01 to current month.
    One row per year_month (not per day).

    Full refresh on every daily run because is_current_month and
    is_complete_month flags are computed relative to CURRENT_DATE()
    and change daily when a new month starts.

    Grain:  one row per year_month
    Schema: gold
    Target: nyc-lakehouse.gold.dim_date

    References:
      - High-Level Architecture §7.6 (dim_date)
      - High-Level Architecture §7.6 note on dim_date grain vs refresh cadence
      - CLAUDE.md §5 (Gold Layer & KPIs)
#}

WITH month_spine AS (

    -- Generate a sequence of months from 2006-01 to current month
    -- Using EXPLODE + SEQUENCE to create the date array
    SELECT
        EXPLODE(
            SEQUENCE(
                DATE '2006-01-01',
                CURRENT_DATE(),
                INTERVAL 1 MONTH
            )
        ) AS month_start

),

formatted AS (

    SELECT
        -- ── Primary key ──
        DATE_FORMAT(month_start, 'yyyy-MM')                         AS year_month,

        -- ── Calendar attributes ──
        YEAR(month_start)                                           AS year,
        MONTH(month_start)                                          AS month,
        QUARTER(month_start)                                        AS quarter,
        DATE_FORMAT(month_start, 'MMMM')                            AS month_name,

        -- ── Temporal flags (computed daily — reason for full refresh) ──
        CASE
            WHEN YEAR(month_start) = YEAR(CURRENT_DATE())
             AND MONTH(month_start) = MONTH(CURRENT_DATE())
            THEN TRUE
            ELSE FALSE
        END                                                         AS is_current_month,

        CASE
            WHEN month_start < DATE_TRUNC('MONTH', CURRENT_DATE())
            THEN TRUE
            ELSE FALSE
        END                                                         AS is_complete_month

    FROM month_spine

)

SELECT
    year_month,
    year,
    month,
    quarter,
    month_name,
    is_current_month,
    is_complete_month,

    -- ── Audit columns ──
    {{ generate_gold_audit_cols() }}

FROM formatted
