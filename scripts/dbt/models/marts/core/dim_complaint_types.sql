{{-
    config(
        materialized='table',
        schema='gold'
    )
-}}

{#
    dim_complaint_types

    Complaint type dimension — one row per distinct 311 complaint type
    with grouped category, subcategory, and responsible agency.

    Full refresh on every run (materialized='table').
    Source: seed_complaint_types (loaded via dbt seed from CSV reference data).

    Grain:  one row per complaint_type
    Schema: gold
    Target: nyc-lakehouse.gold.dim_complaint_types

    References:
      - High-Level Architecture §7.6 (dim_complaint_types)
      - High-Level Architecture §15 (Star Schema)
#}

WITH source AS (

    SELECT
        complaint_type,
        category,
        subcategory,
        responsible_agency
    FROM {{ ref('seed_complaint_types') }}
    WHERE complaint_type IS NOT NULL

)

SELECT
    -- ── Surrogate key ──
    {{ dbt_utils.generate_surrogate_key(['complaint_type']) }}
                                                            AS complaint_type_key,

    -- ── Attributes ──
    complaint_type,
    category,
    subcategory,
    responsible_agency,

    -- ── Audit columns ──
    {{ generate_gold_audit_cols() }}

FROM source
