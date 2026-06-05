{{-
    config(
        materialized='ephemeral'
    )
-}}

{#
    base_dob_permits
    
    Ephemeral base model — handles incremental filtering and deduplication ONLY.
    Column selection drops 33 columns per NYC_Dataset_Analysis §3.
    No type casting here — that's stg_dob_permits' responsibility.

    Dedup key:   job__ + permit_sequence__
    Predicate:   _ingested_at > max(_ingested_at) from target
    Drops:       residential, site_fill, PII (names, phones, addresses),
                 superintendent_*, site_safety_mgr_*, hic_license, permit_si_no,
                 dobrundate, special_district_1, city, state, owner_s_zip_code,
                 permittee_s_first_name, permittee_s_last_name, permittee_s_phone__,
                 permittee_s_license__, owner_s_first_name, owner_s_last_name,
                 owner_s_house__, owner_s_house_street_name,
                 _job_run_id, _notebook_path, _source_system, _rescued_data
    Retains:     30 columns (26 source + 4 ETL metadata)

    NOTE: DOB uses gis_latitude/gis_longitude (not latitude/longitude)
          and job_doc___ (triple underscore) per dataset analysis findings #1 & #4.
#}

WITH source AS (
    SELECT *
    FROM {{ source('bronze', 'dob_permits') }}
    {% if is_incremental() %}
    WHERE _ingested_at > (SELECT MAX(_ingested_at) FROM {{ this }})
    {% endif %}
),

deduped AS (
    SELECT
        -- ── Primary key (composite) ──
        job__,
        permit_sequence__,

        -- ── Identifiers ──
        bin__,
        job_doc___,
        job_type,
        self_cert,

        -- ── Geography ──
        borough,
        house__,
        street_name,
        block,
        lot,
        community_board,
        zip_code,
        bldg_type,
        gis_latitude,
        gis_longitude,
        gis_council_district,
        gis_census_tract,
        gis_nta_name,

        -- ── Permit dimensions ──
        work_type,
        permit_status,
        filing_status,
        permit_type,
        permit_subtype,
        non_profit,
        owner_s_business_type,
        owner_s_business_name,
        permittee_s_business_name,
        permittee_s_license_type,

        -- ── Dates ──
        filing_date,
        issuance_date,
        expiration_date,
        job_start_date,

        -- ── ETL metadata (carried from Bronze) ──
        _row_hash,
        _ingested_at,
        _source_file,
        _ingest_date

    FROM source
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY job__, permit_sequence__
        ORDER BY _ingested_at DESC
    ) = 1
)

SELECT * FROM deduped
