-- complaint_permit_lag_analysis.sql
--
-- dbt Analysis — ad-hoc SQL that answers analytical question Q16:
--
--   "Does construction activity in month T predict a rise in noise
--    complaints in month T+1 or T+2?"
--
-- This is NOT materialised (dbt analyses never run as models).
-- Run it directly via: dbt compile --select complaint_permit_lag_analysis
-- Then execute the compiled SQL in a Databricks notebook or SQL editor.
--
-- Method: self-join int_complaint_permit_corr with 1- and 2-month lag.
-- Databricks Spark SQL uses ADD_MONTHS() for calendar-correct month shifts.
-- The corr CTE then shows: for each zip+month, the permit activity in the
-- prior month and two months prior, alongside the current noise complaints.
--
-- Reading the output:
--   If noise_complaints_t correlates with new_building_count_t_minus_1 or
--   new_building_count_t_minus_2, construction is a leading indicator.
--   Compute Pearson correlation in a notebook to quantify the signal:
--     SELECT corr(new_building_count_t_minus_1, noise_complaints_t) AS r_lag1,
--            corr(new_building_count_t_minus_2, noise_complaints_t) AS r_lag2
--     FROM complaint_permit_lag;
--
-- References:
--   - High-Level Architecture §2 (Analytical Questions — Q16)
--   - High-Level Architecture §7.5 (int_complaint_permit_corr)
--   - int_complaint_permit_corr.sql (the source model)

WITH base AS (

    SELECT
        zip_code,
        year_month,
        noise_complaints,
        construction_complaints,
        total_complaints,
        new_building_count,
        total_permits_issued,
        active_permits
    FROM {{ ref('int_complaint_permit_corr') }}
    -- Exclude sparse months — zips with zero activity in all domains
    -- tend to be business/industrial zones that skew the correlation downward.
    WHERE total_complaints > 0
       OR total_permits_issued > 0

),

-- T-1 lag: permits from the month BEFORE the complaint month
lag_1 AS (

    SELECT
        zip_code,
        year_month,
        new_building_count      AS new_building_count_t_minus_1,
        total_permits_issued    AS total_permits_t_minus_1,
        active_permits          AS active_permits_t_minus_1
    FROM base

),

-- T-2 lag: permits from two months before the complaint month
lag_2 AS (

    SELECT
        zip_code,
        year_month,
        new_building_count      AS new_building_count_t_minus_2,
        total_permits_issued    AS total_permits_t_minus_2
    FROM base

),

complaint_permit_lag AS (

    SELECT
        -- ── Grain: zip + complaint month ──
        b.zip_code,
        b.year_month,

        -- ── Current month signals ──
        b.noise_complaints              AS noise_complaints_t,
        b.construction_complaints       AS construction_complaints_t,
        b.total_complaints              AS total_complaints_t,
        b.new_building_count            AS new_building_count_t,

        -- ── T-1 permit signals (prior month) ──
        l1.new_building_count_t_minus_1,
        l1.total_permits_t_minus_1,
        l1.active_permits_t_minus_1,

        -- ── T-2 permit signals (two months prior) ──
        l2.new_building_count_t_minus_2,
        l2.total_permits_t_minus_2

    FROM base b

    -- Join T-1: complaints in month M join permits in month M-1
    LEFT JOIN lag_1 l1
        ON b.zip_code   = l1.zip_code
       AND b.year_month = DATE_FORMAT(ADD_MONTHS(TO_DATE(CONCAT(l1.year_month, '-01')), 1), 'yyyy-MM')

    -- Join T-2: complaints in month M join permits in month M-2
    LEFT JOIN lag_2 l2
        ON b.zip_code   = l2.zip_code
       AND b.year_month = DATE_FORMAT(ADD_MONTHS(TO_DATE(CONCAT(l2.year_month, '-01')), 2), 'yyyy-MM')

)

SELECT * FROM complaint_permit_lag
ORDER BY zip_code, year_month
