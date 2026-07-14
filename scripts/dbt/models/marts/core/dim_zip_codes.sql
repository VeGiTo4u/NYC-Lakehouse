{{-
    config(
        materialized='table',
        schema='gold'
    )
-}}

{#
    dim_zip_codes

    Zip code dimension — one row per NYC zip code with borough,
    neighborhood name, and NTA code.

    Full refresh on every run (materialized='table').

    Source strategy (two-layer):
      1. seed_zip_codes — curated list with full attributes (borough,
         neighborhood_name, nta_code). Generated from staging data.
      2. Staging fallback — any zip code that appears in actual staging
         records but is NOT in the seed (e.g. NYPD spatial-join zips
         resolved to ZCTA boundary codes not seen in 311/DOB/Restaurant
         data at seed-generation time) gets a dimension row with
         zip + borough only. neighborhood_name and nta_code are NULL.

    When a zip appears in both sources, the seed row wins (ROW_NUMBER).
    This ensures the fact spine never has a zip_code FK with no matching
    dim row, which would fail the relationships test and silently exclude
    arrests from the Neighborhood Pulse Score.

    Grain:  one row per zip_code
    Schema: gold
    Target: nyc-lakehouse.gold.dim_zip_codes

    References:
      - High-Level Architecture §7.6 (dim_zip_codes)
      - High-Level Architecture §15 (Star Schema — dim_zip_codes)
      - High-Level Architecture §5.3 (NYPD spatial join — zip_code_source)
#}

WITH from_seed AS (

    SELECT
        zip_code,
        borough,
        neighborhood_name,
        nta_code,
        1 AS source_priority   -- seed wins on tie
    FROM {{ ref('seed_zip_codes') }}
    WHERE zip_code IS NOT NULL

),

-- Collect every zip_code that appears in actual staging data.
-- Only zip + borough are available here; the other attributes are NULL.
-- ponytail: UNION ALL then dedup is cheaper than 4 separate LEFT JOINs
--           back to the seed. Ceiling: full staging scans on every dim refresh.
--           Upgrade path: materialise a zip_code lookup view in Silver if scans get slow.
from_staging AS (

    SELECT DISTINCT zip_code, borough
    FROM (
        SELECT zip_code, borough FROM {{ ref('stg_311_requests') }}    WHERE zip_code IS NOT NULL
        UNION ALL
        SELECT zip_code, borough FROM {{ ref('stg_nypd_arrests') }}    WHERE zip_code IS NOT NULL AND zip_code != 'UNKNOWN'
        UNION ALL
        SELECT zip_code, borough FROM {{ ref('stg_dob_permits') }}     WHERE zip_code IS NOT NULL
        UNION ALL
        SELECT zip_code, borough FROM {{ ref('stg_restaurant_inspections') }} WHERE zip_code IS NOT NULL
    )

),

-- Staging zips that are NOT already covered by the seed
staging_only AS (

    SELECT
        s.zip_code,
        s.borough,
        CAST(NULL AS STRING)    AS neighborhood_name,
        CAST(NULL AS STRING)    AS nta_code,
        2                       AS source_priority   -- seed always wins
    FROM from_staging s
    WHERE NOT EXISTS (
        SELECT 1 FROM from_seed f WHERE f.zip_code = s.zip_code
    )

),

combined AS (

    SELECT * FROM from_seed
    UNION ALL
    SELECT * FROM staging_only

)

SELECT
    -- ── Primary key ──
    zip_code,

    -- ── Attributes ──
    borough,
    neighborhood_name,
    nta_code,

    -- ── Audit columns ──
    {{ generate_gold_audit_cols() }}

FROM combined
