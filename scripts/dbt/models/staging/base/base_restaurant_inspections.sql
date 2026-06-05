{{-
    config(
        materialized='ephemeral'
    )
-}}

{#
    base_restaurant_inspections
    
    Ephemeral base model — handles incremental filtering and deduplication ONLY.
    Column selection drops 9 columns per NYC_Dataset_Analysis §5.
    No type casting here — that's stg_restaurant_inspections' responsibility.

    Dedup key:   camis + inspection_date + violation_code + inspection_type
                 (inspection_type is required because the same violation_code can
                  appear on both a Cycle Inspection and a Re-inspection on the
                  same date for the same restaurant — per architecture §7.4)
    Predicate:   _ingested_at > max(_ingested_at) from target
    Drops:       phone, record_date, location,
                 _job_run_id, _notebook_path, _source_system, _rescued_data
    Retains:     26 columns (22 source + 4 ETL metadata)
#}

WITH source AS (
    SELECT *
    FROM {{ source('bronze', 'restaurant_inspections') }}
    {% if is_incremental() %}
    WHERE _ingested_at > (SELECT MAX(_ingested_at) FROM {{ this }})
    {% endif %}
),

deduped AS (
    SELECT
        -- ── Primary key (4-part composite) ──
        camis,
        inspection_date,
        violation_code,
        inspection_type,

        -- ── Restaurant dimensions ──
        dba,
        cuisine_description,

        -- ── Geography ──
        boro,
        building,
        street,
        zipcode,
        community_board,
        council_district,
        census_tract,
        bin,
        bbl,
        nta,
        latitude,
        longitude,

        -- ── Inspection results ──
        action,
        violation_description,
        critical_flag,
        score,
        grade,
        grade_date,

        -- ── ETL metadata (carried from Bronze) ──
        _row_hash,
        _ingested_at,
        _source_file,
        _ingest_date

    FROM source
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY camis, inspection_date, violation_code, inspection_type
        ORDER BY _ingested_at DESC
    ) = 1
)

SELECT * FROM deduped
