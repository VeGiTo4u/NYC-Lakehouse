-- assert_no_null_pulse_score.sql
--
-- Custom singular test: Verifies neighborhood_pulse_score IS NOT NULL
-- for every row in fact_neighborhood_monthly.
--
-- A NULL score means the COALESCE guards around the measures failed
-- — all measures must be wrapped in COALESCE(measure, 0) to prevent
-- a single NULL from wiping out the entire zip code's score.
--
-- Returns failing rows (should return 0 rows to pass).
--
-- References:
--   - High-Level Architecture §12 (Data Quality — assert_no_null_pulse_score)
--   - CLAUDE.md §5 (NULL Safety in KPIs)

SELECT
    zip_code,
    year_month,
    neighborhood_pulse_score
FROM {{ ref('fact_neighborhood_monthly') }}
WHERE neighborhood_pulse_score IS NULL
