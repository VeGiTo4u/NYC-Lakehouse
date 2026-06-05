{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='permit_key'
    )
-}}

{#
    stg_dob_permits

    Staged DOB permit issuance records — the final Silver output for DOB data.
    Reads from base_dob_permits (ephemeral — already deduplicated).
    
    Transformations:
      - Surrogate key: dbt_utils.generate_surrogate_key on [job__, permit_sequence__]
      - Type casting: dates → DATE, coords → DOUBLE
      - Renaming: gis_latitude → latitude, gis_longitude → longitude (per finding #1)
      - Uses job_doc___ (triple underscore — per finding #4)
      - Borough standardisation (numeric codes 1-5)
      - Derived columns: year_month, is_active_permit
      - Audit columns via macro

    Grain:     one row per job_number + permit_sequence_number
    Unique key: permit_key (surrogate)
    Target:    nyc-lakehouse.silver.stg_dob_permits

    References:
      - High-Level Architecture §7.4 (stg_dob_permits)
      - NYC_Dataset_Analysis §3 (DOB column decisions)
      - NYC_Dataset_Analysis §9.3 findings #1 (gis_latitude) and #4 (job_doc___)
#}

WITH base AS (
    SELECT * FROM {{ ref('base_dob_permits') }}
),

staged AS (
    SELECT
        -- ── Surrogate key (for merge unique_key) ──
        {{ dbt_utils.generate_surrogate_key(['job__', 'permit_sequence__']) }}
                                                                    AS permit_key,

        -- ── Primary key (composite — natural) ──
        TRIM(job__)                                                 AS job_number,
        TRIM(permit_sequence__)                                     AS permit_sequence_number,

        -- ── Identifiers ──
        TRIM(bin__)                                                 AS building_id_number,
        TRIM(job_doc___)                                            AS job_document_number,
        TRIM(job_type)                                              AS job_type,
        TRIM(self_cert)                                             AS is_self_certified,

        -- ── Geography (renamed + standardised) ──
        TRIM(borough)                                               AS borough_raw,
        {{ standardize_borough('borough') }}                        AS borough,
        TRIM(house__)                                               AS house_number,
        TRIM(street_name)                                           AS street_name,
        TRIM(block)                                                 AS tax_block,
        TRIM(lot)                                                   AS tax_lot,
        TRIM(community_board)                                       AS community_board,
        TRIM(zip_code)                                              AS zip_code,
        TRIM(bldg_type)                                             AS building_type,
        -- DOB uses gis_latitude / gis_longitude (not latitude / longitude)
        TRY_CAST(gis_latitude AS DOUBLE)                            AS latitude,
        TRY_CAST(gis_longitude AS DOUBLE)                           AS longitude,
        TRIM(gis_council_district)                                  AS council_district,
        TRIM(gis_census_tract)                                      AS census_tract,
        TRIM(gis_nta_name)                                          AS neighborhood_name,

        -- ── Permit dimensions ──
        TRIM(work_type)                                             AS work_type,
        TRIM(permit_status)                                         AS permit_status,
        TRIM(filing_status)                                         AS filing_status,
        TRIM(permit_type)                                           AS permit_type,
        TRIM(permit_subtype)                                        AS permit_subtype,
        TRIM(non_profit)                                            AS is_non_profit,
        TRIM(owner_s_business_type)                                 AS owner_business_type,
        TRIM(owner_s_business_name)                                 AS owner_business_name,
        TRIM(permittee_s_business_name)                             AS permittee_business_name,
        TRIM(permittee_s_license_type)                              AS permittee_license_type,

        -- ── Dates (type-cast to DATE) ──
        TRY_CAST(filing_date AS DATE)                               AS filing_date,
        TRY_CAST(issuance_date AS DATE)                             AS issuance_date,
        TRY_CAST(expiration_date AS DATE)                           AS expiration_date,
        TRY_CAST(job_start_date AS DATE)                            AS job_start_date,

        -- ── Derived columns ──
        CASE
            WHEN TRY_CAST(expiration_date AS DATE) >= CURRENT_DATE() THEN 1
            ELSE 0
        END                                                         AS is_active_permit,
        DATE_FORMAT(TRY_CAST(issuance_date AS DATE), 'yyyy-MM')    AS year_month,

        -- ── Audit & metadata columns ──
        {{ generate_staging_audit_cols() }}

    FROM base
)

SELECT * FROM staged
