{{-
    config(
        materialized='ephemeral'
    )
-}}

{#
    base_nypd_arrests
    
    Ephemeral base model — handles incremental filtering and deduplication ONLY.
    Column selection drops 11 columns per NYC_Dataset_Analysis §4.
    No type casting here — that's stg_nypd_arrests' responsibility.

    Dedup key:   arrest_key
    Predicate:   _ingested_at > max(_ingested_at) from target
    Drops:       jurisdiction_code, x_coord_cd, y_coord_cd, lon_lat,
                 geocoded_column,
                 _job_run_id, _notebook_path, _source_system, _rescued_data
    Retains:     17 columns (13 source + 4 ETL metadata)

    IMPORTANT: Dedup runs BEFORE the spatial join in stg_nypd_arrests
    to avoid wasted st_contains calls on duplicate rows (per CLAUDE.md §3).
#}

WITH source AS (
    SELECT *
    FROM {{ source('bronze', 'nypd_arrests') }}
    {% if is_incremental() %}
    WHERE _ingested_at > (SELECT MAX(_ingested_at) FROM {{ this }})
    {% endif %}
),

deduped AS (
    SELECT
        -- ── Primary key ──
        arrest_key,

        -- ── Dates ──
        arrest_date,

        -- ── Offense dimensions ──
        pd_cd,
        pd_desc,
        ky_cd,
        ofns_desc,
        law_code,
        law_cat_cd,

        -- ── Geography ──
        arrest_boro,
        arrest_precinct,

        -- ── Demographics ──
        age_group,
        perp_sex,
        perp_race,

        -- ── Spatial join inputs ──
        latitude,
        longitude,

        -- ── ETL metadata (carried from Bronze) ──
        _row_hash,
        _ingested_at,
        _source_file,
        _ingest_date

    FROM source
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY arrest_key
        ORDER BY _ingested_at DESC
    ) = 1
)

SELECT * FROM deduped
