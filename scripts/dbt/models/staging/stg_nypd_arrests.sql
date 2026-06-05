{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='arrest_id'
    )
-}}

{#
    stg_nypd_arrests

    Staged NYPD arrest records — the final Silver output for NYPD data.
    Reads from base_nypd_arrests (ephemeral — already deduplicated).
    
    Two-step CTE order (per CLAUDE.md §3):
      1. base_nypd_arrests handles dedup FIRST (QUALIFY on arrest_key)
      2. This model performs spatial join AFTER dedup to avoid wasted st_contains calls

    Transformations:
      - Type casting: arrest_date → DATE, PK → BIGINT, coords → DOUBLE, precinct → INT
      - Borough standardisation (single-letter codes: M/B/K/Q/S)
      - NULLIF on age_group and perp_sex for literal '(null)' strings (dataset analysis finding #2)
      - Spatial join via macro → zip_code + zip_code_source
      - Dedup after spatial join (boundary overlaps can match multiple ZCTA polygons)
      - Derived columns: year_month
      - Audit columns via macro

    Grain:     one row per arrest_id
    Unique key: arrest_id
    Target:    nyc-lakehouse.silver.stg_nypd_arrests

    References:
      - High-Level Architecture §7.4 (stg_nypd_arrests — dedup → spatial join)
      - High-Level Architecture §5.3 (Spatial Join — st_contains)
      - NYC_Dataset_Analysis §4 (NYPD column decisions)
      - NYC_Dataset_Analysis §9.3 findings #2 (NULLIF) and #3 (law_cat_cd values)
#}

WITH base AS (
    SELECT * FROM {{ ref('base_nypd_arrests') }}
),

type_cast AS (
    SELECT
        -- ── Primary key ──
        TRY_CAST(arrest_key AS BIGINT)                                AS arrest_id,

        -- ── Dates ──
        TRY_CAST(arrest_date AS DATE)                                 AS arrest_date,

        -- ── Offense dimensions ──
        TRY_CAST(pd_cd AS INT)                                        AS nypd_classification_code,
        TRIM(pd_desc)                                               AS nypd_classification_desc,
        TRY_CAST(ky_cd AS INT)                                        AS offense_category_code,
        TRIM(ofns_desc)                                             AS offense_description,
        TRIM(law_code)                                              AS penal_law_code,
        CASE UPPER(TRIM(law_cat_cd))
            WHEN '' THEN NULL
            WHEN 'NAN' THEN NULL
            WHEN '(NULL)' THEN NULL
            ELSE UPPER(TRIM(law_cat_cd))
        END                                                         AS law_category,

        -- ── Geography (standardised) ──
        TRIM(arrest_boro)                                           AS arrest_borough_raw,
        {{ standardize_borough('arrest_boro') }}                    AS borough,
        TRY_CAST(arrest_precinct AS INT)                              AS arrest_precinct,

        -- ── Demographics (NULLIF for literal '(null)' strings) ──
        NULLIF(TRIM(age_group), '(null)')                           AS perpetrator_age_group,
        NULLIF(TRIM(perp_sex), '(null)')                            AS perpetrator_sex,
        TRIM(perp_race)                                             AS perpetrator_race,

        -- ── Spatial join inputs (type-cast) ──
        TRY_CAST(latitude AS DOUBLE)                                  AS latitude,
        TRY_CAST(longitude AS DOUBLE)                                 AS longitude,

        -- ── ETL metadata (carried from Bronze) ──
        _row_hash,
        _ingested_at,
        _source_file,
        _ingest_date

    FROM base
),

-- Spatial join: assign zip_code via st_contains against ZCTA polygons
with_zip AS (
    {{ spatial_zip_join('type_cast', 'latitude', 'longitude') }}
),

-- Collapse boundary overlaps — one row per arrest_id
with_zip_deduped AS (
    SELECT *
    FROM with_zip
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY arrest_id
        ORDER BY
            CASE WHEN zip_code_source = 'spatial' THEN 0 ELSE 1 END,
            zip_code
    ) = 1
),

staged AS (
    SELECT
        arrest_id,
        arrest_date,
        nypd_classification_code,
        nypd_classification_desc,
        offense_category_code,
        offense_description,
        penal_law_code,
        law_category,
        arrest_borough_raw,
        borough,
        arrest_precinct,
        perpetrator_age_group,
        perpetrator_sex,
        perpetrator_race,
        latitude,
        longitude,
        zip_code,
        zip_code_source,
        DATE_FORMAT(arrest_date, 'yyyy-MM')                         AS year_month,
        {{ generate_staging_audit_cols() }}

    FROM with_zip_deduped
)

SELECT * FROM staged
