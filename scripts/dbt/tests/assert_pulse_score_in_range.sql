-- assert_pulse_score_in_range.sql
--
-- Custom singular test: Verifies neighborhood_pulse_score is between
-- 0 and 100 (inclusive) for every row in fact_neighborhood_monthly.
--
-- The formula is designed to produce values in [0, 100]. A value
-- outside this range indicates a bug in the formula weights or
-- a missing LEAST() cap.
--
-- Returns failing rows (should return 0 rows to pass).
--
-- References:
--   - High-Level Architecture §12 (Data Quality — assert_pulse_score_in_range)
--   - High-Level Architecture §7.6 (Neighborhood Pulse Score Formula)

SELECT
    zip_code,
    year_month,
    neighborhood_pulse_score
FROM {{ ref('fact_neighborhood_monthly') }}
WHERE neighborhood_pulse_score < 0
   OR neighborhood_pulse_score > 100
