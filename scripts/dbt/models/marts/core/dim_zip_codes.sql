{{-
    config(
        materialized='table',
        schema='gold',
        location_root='s3://nyc-lakehouse-store/gold/core'
    )
-}}

{#
    dim_zip_codes

    Zip code dimension — one row per NYC zip code with borough,
    neighborhood name, and NTA code.

    Full refresh on every run (materialized='table').
    Source: seed_zip_codes (loaded via dbt seed from CSV reference data).

    Grain:  one row per zip_code
    Schema: gold
    Target: nyc-lakehouse.gold.dim_zip_codes

    References:
      - High-Level Architecture §7.6 (dim_zip_codes)
      - High-Level Architecture §15 (Star Schema — dim_zip_codes)
#}

WITH source AS (

    SELECT
        zip_code,
        borough,
        neighborhood_name,
        nta_code
    FROM {{ ref('seed_zip_codes') }}
    WHERE zip_code IS NOT NULL

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

FROM source
