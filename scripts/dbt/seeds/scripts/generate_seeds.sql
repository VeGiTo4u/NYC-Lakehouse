-- ═══════════════════════════════════════════════════════════════════
-- generate_seeds.sql
--
-- Databricks SQL script to extract dimension reference data from
-- Silver staging tables and produce CSV-ready output for dbt seeds.
--
-- Run each query in Databricks SQL Editor and export results as CSV
-- to the corresponding seed file in scripts/dbt/seeds/.
--
-- References:
--   - Implementation Plan §2 (Seed CSVs)
--   - High-Level Architecture §7.6 (Gold Dimension Tables)
-- ═══════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────
-- 1. seed_zip_codes.csv
--    Source: All 4 staging models + DOB neighborhood enrichment
--    Grain: One row per distinct zip_code
-- ─────────────────────────────────────────────────────────────────

WITH all_zips AS (
    -- Collect zip_code + borough from all staging sources
    SELECT zip_code, borough FROM `nyc-lakehouse`.silver.stg_311_requests WHERE zip_code IS NOT NULL
    UNION
    SELECT zip_code, borough FROM `nyc-lakehouse`.silver.stg_nypd_arrests WHERE zip_code IS NOT NULL AND zip_code != 'UNKNOWN'
    UNION
    SELECT zip_code, borough FROM `nyc-lakehouse`.silver.stg_dob_permits WHERE zip_code IS NOT NULL
    UNION
    SELECT zip_code, borough FROM `nyc-lakehouse`.silver.stg_restaurant_inspections WHERE zip_code IS NOT NULL
),

-- Pick the most frequent borough for each zip code (consensus across sources)
borough_consensus AS (
    SELECT
        zip_code,
        borough,
        ROW_NUMBER() OVER (
            PARTITION BY zip_code
            ORDER BY COUNT(*) DESC, borough
        ) AS rn
    FROM all_zips
    WHERE borough IS NOT NULL
    GROUP BY zip_code, borough
),

-- Enrich with DOB neighborhood data (most recent per zip)
dob_enrichment AS (
    SELECT
        zip_code,
        neighborhood_name,
        neighborhood_tabulation_area AS nta_code,
        ROW_NUMBER() OVER (
            PARTITION BY zip_code
            ORDER BY issuance_date DESC
        ) AS rn
    FROM `nyc-lakehouse`.silver.stg_dob_permits
    WHERE zip_code IS NOT NULL
      AND neighborhood_name IS NOT NULL
)

SELECT
    b.zip_code,
    b.borough,
    d.neighborhood_name,
    d.nta_code
FROM borough_consensus b
LEFT JOIN dob_enrichment d
    ON b.zip_code = d.zip_code AND d.rn = 1
WHERE b.rn = 1
ORDER BY b.zip_code;


-- ─────────────────────────────────────────────────────────────────
-- 2. seed_complaint_types.csv
--    Source: stg_311_requests
--    Grain: One row per distinct complaint_type
-- ─────────────────────────────────────────────────────────────────

WITH complaint_data AS (
    SELECT
        complaint_type,
        complaint_descriptor,
        responding_agency_code,
        ROW_NUMBER() OVER (
            PARTITION BY complaint_type
            ORDER BY COUNT(*) DESC
        ) AS rn
    FROM `nyc-lakehouse`.silver.stg_311_requests
    WHERE complaint_type IS NOT NULL
    GROUP BY complaint_type, complaint_descriptor, responding_agency_code
)

SELECT
    complaint_type,
    CASE
        WHEN complaint_type LIKE '%Noise%' THEN 'Noise'
        WHEN complaint_type LIKE '%Food%' THEN 'Food'
        WHEN complaint_type LIKE '%Construction%' OR complaint_type LIKE '%Building%' THEN 'Construction'
        WHEN complaint_type LIKE '%Heat%' OR complaint_type LIKE '%Hot Water%' THEN 'Housing'
        WHEN complaint_type LIKE '%Water%' OR complaint_type LIKE '%Sewer%' THEN 'Infrastructure'
        WHEN complaint_type LIKE '%Street%' OR complaint_type LIKE '%Sidewalk%' THEN 'Streets'
        WHEN complaint_type LIKE '%Sanit%' OR complaint_type LIKE '%Trash%' OR complaint_type LIKE '%Dirty%' THEN 'Sanitation'
        ELSE 'Other'
    END AS category,
    complaint_descriptor AS subcategory,
    responding_agency_code AS responsible_agency
FROM complaint_data
WHERE rn = 1
ORDER BY complaint_type;


-- ─────────────────────────────────────────────────────────────────
-- 3. seed_permit_types.csv
--    Source: stg_dob_permits
--    Grain: One row per distinct permit_type
-- ─────────────────────────────────────────────────────────────────

WITH permit_data AS (
    SELECT
        permit_type,
        permit_subtype,
        job_type,
        work_type,
        ROW_NUMBER() OVER (
            PARTITION BY permit_type
            ORDER BY COUNT(*) DESC
        ) AS rn
    FROM `nyc-lakehouse`.silver.stg_dob_permits
    WHERE permit_type IS NOT NULL
    GROUP BY permit_type, permit_subtype, job_type, work_type
)

SELECT
    permit_type,
    permit_subtype AS permit_type_desc,
    job_type,
    CASE
        WHEN job_type = 'NB' THEN 'New Building'
        WHEN job_type IN ('A1', 'A2', 'A3') THEN 'Alteration'
        WHEN job_type = 'DM' THEN 'Demolition'
        WHEN job_type = 'SG' THEN 'Sign'
        WHEN job_type = 'FO' THEN 'Foundation'
        ELSE 'Other'
    END AS work_category
FROM permit_data
WHERE rn = 1
ORDER BY permit_type;
