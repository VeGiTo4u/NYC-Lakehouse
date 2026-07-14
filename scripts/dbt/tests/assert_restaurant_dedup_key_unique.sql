-- assert_restaurant_dedup_key_unique.sql
--
-- Custom singular test: Validates that the 4-part dedup key
-- (restaurant_id + inspection_date + violation_code + inspection_type)
-- is unique in stg_restaurant_inspections.
--
-- Why 4 columns: the same violation_code can appear on both a
-- Cycle Inspection and a Re-inspection on the same date for the same
-- restaurant. Without inspection_type the key has silent collisions and
-- rows are incorrectly dropped in the QUALIFY dedup step.
--
-- Returns duplicate rows (should return 0 rows to pass).
--
-- References:
--   - High-Level Architecture §12 (Data Quality — assert_restaurant_dedup_key_unique)
--   - NYC_Dataset_Analysis §1 finding #8 (316 unique camis, ~3.2 rows per restaurant)
--   - High-Level Architecture §7.4 (stg_restaurant_inspections dedup key)

SELECT
    restaurant_id,
    inspection_date,
    violation_code,
    inspection_type,
    COUNT(*) AS duplicate_count
FROM {{ ref('stg_restaurant_inspections') }}
GROUP BY
    restaurant_id,
    inspection_date,
    violation_code,
    inspection_type
HAVING COUNT(*) > 1
