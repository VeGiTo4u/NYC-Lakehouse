-- assert_no_future_dates.sql
--
-- Custom singular test: Verifies that no source date column in any
-- staging model contains a date beyond CURRENT_DATE().
--
-- Why this matters: DOB permits have projected expiry dates far in the
-- future. A Bronze schema mismatch or API field swap could land a future
-- date in the watermark column, silently attributing records to a future
-- year_month and corrupting incremental aggregations.
--
-- Each dataset uses its own time-grain column (per HLA §5.1):
--   311         → created_date (TIMESTAMP — cast to DATE for comparison)
--   NYPD        → arrest_date  (DATE)
--   DOB         → issuance_date (DATE)  ← expiration_date intentionally excluded
--   Restaurant  → inspection_date (DATE)
--
-- Returns failing rows (should return 0 rows to pass).
--
-- References:
--   - High-Level Architecture §12 (Data Quality — assert_no_future_dates)
--   - NYC_Dataset_Analysis §3 (DOB — issuance_date is the watermark column)

SELECT '311' AS source, complaint_id AS record_id, CAST(created_date AS DATE) AS bad_date
FROM {{ ref('stg_311_requests') }}
WHERE CAST(created_date AS DATE) > CURRENT_DATE()

UNION ALL

SELECT 'nypd', CAST(arrest_id AS STRING), arrest_date
FROM {{ ref('stg_nypd_arrests') }}
WHERE arrest_date > CURRENT_DATE()

UNION ALL

SELECT 'dob', permit_key, issuance_date
FROM {{ ref('stg_dob_permits') }}
WHERE issuance_date > CURRENT_DATE()

UNION ALL

SELECT 'restaurant', inspection_record_key, inspection_date
FROM {{ ref('stg_restaurant_inspections') }}
WHERE inspection_date > CURRENT_DATE()
