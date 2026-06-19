{{-
    config(
        materialized='table',
        schema='gold',
        location_root='s3://nyc-lakehouse-store/gold/core'
    )
-}}

{#
    dim_permit_types

    Permit type dimension — one row per distinct DOB permit type
    with description, job type code, and derived work category.

    Full refresh on every run (materialized='table').
    Source: seed_permit_types (loaded via dbt seed from CSV reference data).

    Grain:  one row per permit_type
    Schema: gold
    Target: nyc-lakehouse.gold.dim_permit_types

    References:
      - High-Level Architecture §7.6 (dim_permit_types)
      - High-Level Architecture §15 (Star Schema)
#}

WITH source AS (

    SELECT
        permit_type,
        permit_type_desc,
        job_type,
        work_category
    FROM {{ ref('seed_permit_types') }}
    WHERE permit_type IS NOT NULL

)

SELECT
    -- ── Surrogate key ──
    {{ dbt_utils.generate_surrogate_key(['permit_type']) }}
                                                            AS permit_type_key,

    -- ── Attributes ──
    permit_type,
    permit_type_desc,
    job_type,
    work_category,

    -- ── Audit columns ──
    {{ generate_gold_audit_cols() }}

FROM source
