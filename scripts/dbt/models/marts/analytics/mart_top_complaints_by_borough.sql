{{-
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['borough', 'year_month', 'complaint_type'],
        schema='gold',
        location_root='s3://nyc-lakehouse-store/gold/analytics'
    )
-}}

{#
    mart_top_complaints_by_borough

    Complaint type rankings per borough per month — aggregates raw
    311 complaint data to borough + year_month + complaint_type grain
    with ranked complaint volumes.

    Sources directly from stg_311_requests (not intermediate) because
    the intermediate model aggregated away complaint_type detail.

    Grain:     borough + year_month + complaint_type
    Unique key: [borough, year_month, complaint_type]
    Strategy:  Incremental MERGE with 90-day lookback
    Source:    stg_311_requests
    Schema:    gold
    Target:    nyc-lakehouse.gold.mart_top_complaints_by_borough

    References:
      - High-Level Architecture §7.6 (mart_top_complaints_by_borough)
      - High-Level Architecture §7.8 (Streamlit — Complaint Intelligence page)
#}

WITH source AS (

    SELECT
        borough,
        year_month,
        complaint_type
    FROM {{ ref('stg_311_requests') }}
    WHERE borough IS NOT NULL
      AND year_month IS NOT NULL
      AND complaint_type IS NOT NULL
    {% if is_incremental() %}
      AND year_month >= DATE_FORMAT(
          DATE_SUB(CURRENT_DATE(), {{ var('lookback_days_default') }}),
          'yyyy-MM'
      )
    {% endif %}

),

aggregated AS (

    SELECT
        borough,
        year_month,
        complaint_type,

        -- ── Volume ──
        COUNT(*)                                                    AS complaint_count

    FROM source
    GROUP BY borough, year_month, complaint_type

),

ranked AS (

    SELECT
        borough,
        year_month,
        complaint_type,
        complaint_count,

        -- ── Ranking within borough + month ──
        DENSE_RANK() OVER (
            PARTITION BY borough, year_month
            ORDER BY complaint_count DESC
        )                                                           AS borough_rank,

        -- ── Percentage of borough total ──
        ROUND(
            complaint_count * 1.0
            / SUM(complaint_count) OVER (PARTITION BY borough, year_month),
            4
        )                                                           AS pct_of_borough_total

    FROM aggregated

)

SELECT
    borough,
    year_month,
    complaint_type,
    complaint_count,
    borough_rank,
    pct_of_borough_total,

    -- ── Audit columns ──
    {{ generate_gold_audit_cols() }}

FROM ranked
