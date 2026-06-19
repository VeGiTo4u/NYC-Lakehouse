-- assert_no_null_zip_in_fact.sql
--
-- Custom singular test: Verifies no NULL zip_code values exist in
-- fact_neighborhood_monthly. The zip_month_spine should guarantee
-- every row has a zip_code, so any NULL indicates a spine issue.
--
-- Returns failing rows (should return 0 rows to pass).
--
-- References:
--   - High-Level Architecture §12 (Data Quality — assert_no_null_zip_in_fact)

SELECT
    zip_code,
    year_month
FROM {{ ref('fact_neighborhood_monthly') }}
WHERE zip_code IS NULL
