{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='inspection_record_key'
    )
-}}

{#
    stg_restaurant_inspections

    Staged restaurant inspection records — the final Silver output.
    Reads from base_restaurant_inspections (ephemeral — already deduplicated on
    4-part composite key: camis + inspection_date + violation_code + inspection_type).
    
    Transformations:
      - Surrogate key for merge on 4-part composite
      - Type casting: dates → DATE, score → INT, coords → DOUBLE
      - Renaming: boro → borough, zipcode → zip_code, camis → restaurant_id
      - Borough standardisation (mixed-case full names)
      - Derived columns: year_month, grade_numeric
      - Audit columns via macro

    NOTE on grade NULLs: 49.7% NULL grades are expected by design — initial
    inspections don't get graded. Do NOT treat as data quality issue.

    Grain:     one row per restaurant_id + inspection_date + violation_code + inspection_type
    Unique key: inspection_record_key (surrogate)
    Target:    nyc-lakehouse.silver.stg_restaurant_inspections

    References:
      - High-Level Architecture §7.4 (stg_restaurant_inspections)
      - NYC_Dataset_Analysis §5 (Restaurant column decisions)
#}

WITH base AS (
    SELECT * FROM {{ ref('base_restaurant_inspections') }}
),

staged AS (
    SELECT
        -- ── Surrogate key (for merge unique_key) ──
        {{ dbt_utils.generate_surrogate_key([
            'camis', 'inspection_date', 'violation_code', 'inspection_type'
        ]) }}                                                       AS inspection_record_key,

        -- ── Primary key (4-part composite — natural) ──
        TRIM(camis)                                                 AS restaurant_id,
        TRY_CAST(inspection_date AS DATE)                             AS inspection_date,
        TRIM(violation_code)                                        AS violation_code,
        TRIM(inspection_type)                                       AS inspection_type,

        -- ── Restaurant dimensions ──
        TRIM(dba)                                                   AS restaurant_name,
        TRIM(cuisine_description)                                   AS cuisine_type,

        -- ── Geography (renamed + standardised) ──
        TRIM(boro)                                                  AS borough_raw,
        {{ standardize_borough('boro') }}                           AS borough,
        TRIM(building)                                              AS building_number,
        TRIM(street)                                                AS street_name,
        TRIM(zipcode)                                               AS zip_code,
        TRIM(community_board)                                       AS community_board,
        TRIM(council_district)                                      AS council_district,
        TRIM(census_tract)                                          AS census_tract,
        TRIM(bin)                                                   AS building_id_number,
        TRY_CAST(bbl AS NUMERIC)                                    AS borough_block_lot,
        TRIM(nta)                                                   AS neighborhood_tabulation_area,
        TRY_CAST(latitude AS DOUBLE)                                AS latitude,
        TRY_CAST(longitude AS DOUBLE)                               AS longitude,

        -- ── Inspection results ──
        TRIM(action)                                                AS enforcement_action,
        TRIM(violation_description)                                 AS violation_description,
        TRIM(critical_flag)                                         AS is_critical_violation,
        TRY_CAST(score AS INT)                                      AS inspection_score,
        CASE UPPER(TRIM(grade))
            WHEN '' THEN NULL
            WHEN 'NAN' THEN NULL
            WHEN '(NULL)' THEN NULL
            ELSE UPPER(TRIM(grade))
        END                                                         AS inspection_grade,
        TRY_CAST(grade_date AS DATE)                                AS grade_assigned_date,

        -- ── Derived columns ──
        CASE
            WHEN UPPER(TRIM(grade)) = 'A' THEN 1
            WHEN UPPER(TRIM(grade)) = 'B' THEN 2
            WHEN UPPER(TRIM(grade)) = 'C' THEN 3
            ELSE NULL
        END                                                         AS grade_numeric,
        DATE_FORMAT(TRY_CAST(inspection_date AS DATE), 'yyyy-MM')  AS year_month,

        -- ── Audit & metadata columns ──
        {{ generate_staging_audit_cols() }}

    FROM base
)

SELECT * FROM staged
