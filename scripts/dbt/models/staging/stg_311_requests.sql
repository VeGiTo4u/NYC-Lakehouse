{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='complaint_id'
    )
-}}

{#
    stg_311_requests

    Staged 311 service requests — the final Silver output for 311 data.
    Reads from base_311_requests (ephemeral — already deduplicated).
    
    Transformations:
      - Type casting: dates → TIMESTAMP, PK → BIGINT, coords → DOUBLE
      - Renaming: incident_zip → zip_code, unique_key → complaint_id
      - Borough standardisation via macro
      - Derived columns: resolution_time_hours, year_month
      - Audit columns via macro

    Grain:     one row per complaint_id
    Unique key: complaint_id
    Target:    nyc-lakehouse.silver.stg_311_requests
    
    References:
      - High-Level Architecture §7.4 (stg_311_requests)
      - NYC_Dataset_Analysis §2 (311 column decisions)
      - CLAUDE.md §3 (dedup must be FIRST step — handled in base model)
#}

WITH base AS (
    SELECT * FROM {{ ref('base_311_requests') }}
),

staged AS (
    SELECT
        -- ── Primary key ──
        TRY_CAST(unique_key AS BIGINT)                                AS complaint_id,

        -- ── Dates (type-cast to TIMESTAMP — TRY_CAST tolerates 'nan' values) ──
        TRY_CAST(created_date AS TIMESTAMP)                           AS created_date,
        TRY_CAST(closed_date AS TIMESTAMP)                            AS closed_date,
        TRY_CAST(resolution_action_updated_date AS TIMESTAMP)         AS resolution_action_updated_date,

        -- ── Complaint dimensions ──
        TRIM(agency)                                                AS responding_agency_code,
        TRIM(complaint_type)                                        AS complaint_type,
        TRIM(descriptor)                                            AS complaint_descriptor,
        TRIM(location_type)                                         AS location_type,
        CASE UPPER(TRIM(status))
            WHEN 'OPEN' THEN 'Open'
            WHEN 'CLOSED' THEN 'Closed'
            WHEN 'PENDING' THEN 'Pending'
            WHEN 'STARTED' THEN 'Started'
            WHEN 'ASSIGNED' THEN 'Assigned'
            WHEN 'IN PROGRESS' THEN 'In Progress'
            WHEN 'IN_PROGRESS' THEN 'In Progress'
            WHEN 'DRAFT' THEN 'Draft'
            WHEN '' THEN 'Unspecified'
            WHEN 'UNSPECIFIED' THEN 'Unspecified'
            ELSE 'Unspecified'
        END                                                         AS complaint_status,
        TRIM(resolution_description)                                AS resolution_description,
        TRIM(open_data_channel_type)                                AS submission_channel,

        -- ── Geography (renamed + standardised) ──
        TRIM(incident_zip)                                          AS zip_code,
        TRIM(incident_address)                                      AS incident_address,
        TRIM(street_name)                                           AS street_name,
        TRIM(cross_street_1)                                        AS cross_street_1,
        TRIM(cross_street_2)                                        AS cross_street_2,
        TRIM(city)                                                  AS city,
        CASE UPPER(TRIM(borough))
            WHEN '' THEN NULL
            WHEN 'UNSPECIFIED' THEN NULL
            WHEN 'NAN' THEN NULL
            WHEN '(NULL)' THEN NULL
            ELSE TRIM(borough)
        END                                                         AS borough_raw,
        {{ standardize_borough('borough') }}                        AS borough,
        TRIM(community_board)                                       AS community_board,
        TRIM(council_district)                                      AS council_district,
        TRIM(police_precinct)                                       AS police_precinct,
        TRY_CAST(bbl AS NUMERIC)                                    AS borough_block_lot,
        TRY_CAST(latitude AS DOUBLE)                                AS latitude,
        TRY_CAST(longitude AS DOUBLE)                               AS longitude,

        -- ── Derived columns ──
        TIMESTAMPDIFF(
            HOUR,
            TRY_CAST(created_date AS TIMESTAMP),
            TRY_CAST(closed_date AS TIMESTAMP)
        )                                                           AS resolution_time_hours,
        DATE_FORMAT(TRY_CAST(created_date AS TIMESTAMP), 'yyyy-MM') AS year_month,

        -- ── Audit & metadata columns ──
        {{ generate_staging_audit_cols() }}

    FROM base
)

SELECT * FROM staged
