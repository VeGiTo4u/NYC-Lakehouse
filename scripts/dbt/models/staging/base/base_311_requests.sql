{{-
    config(
        materialized='ephemeral'
    )
-}}

{#
    base_311_requests
    
    Ephemeral base model — handles incremental filtering and deduplication ONLY.
    Column selection drops 23 columns per NYC_Dataset_Analysis §2.
    No type casting here — that's stg_311_requests' responsibility.

    Dedup key:   unique_key
    Predicate:   _ingested_at > max(_ingested_at) from target
    Drops:       agency_name, intersection_street_1/2, location, park_facility_name,
                 park_borough, x/y_coordinate_state_plane, descriptor_2, address_type,
                 taxi_pick_up_location, facility_type, taxi_company_borough,
                 bridge_highway_name/direction/segment, road_ramp, due_date,
                 vehicle_type, landmark,
                 _job_run_id, _notebook_path, _source_system, _rescued_data
    Retains:     29 columns (25 source + 4 ETL metadata)
#}

WITH source AS (
    SELECT *
    FROM {{ source('bronze', '311_requests') }}
    {% if is_incremental() %}
    WHERE _ingested_at > (SELECT MAX(_ingested_at) FROM {{ this }})
    {% endif %}
),

deduped AS (
    SELECT
        -- ── Primary key ──
        unique_key,

        -- ── Dates ──
        created_date,
        closed_date,
        resolution_action_updated_date,

        -- ── Complaint dimensions ──
        agency,
        complaint_type,
        descriptor,
        location_type,
        status,
        resolution_description,
        open_data_channel_type,

        -- ── Geography ──
        incident_zip,
        incident_address,
        street_name,
        cross_street_1,
        cross_street_2,
        city,
        borough,
        community_board,
        council_district,
        police_precinct,
        bbl,
        latitude,
        longitude,

        -- ── ETL metadata (carried from Bronze) ──
        _row_hash,
        _ingested_at,
        _source_file,
        _ingest_date

    FROM source
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY unique_key
        ORDER BY _ingested_at DESC
    ) = 1
)

SELECT * FROM deduped
