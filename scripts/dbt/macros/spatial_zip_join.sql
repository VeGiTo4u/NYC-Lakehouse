{#
    spatial_zip_join(cte_ref, lat_col, lon_col)

    Wraps the Databricks st_contains point-in-polygon spatial join that assigns
    a zip code to each NYPD arrest row using the NYC ZCTA shapefile.

    - One arrest → one zip code (no fan-out, no duplication)
    - Arrests with NULL or unmatched coordinates → zip_code = 'UNKNOWN',
      zip_code_source = 'borough_fallback'

    Args:
      cte_ref  : Name of the upstream CTE (string, not ref — used as alias)
      lat_col  : Latitude column name in the CTE
      lon_col  : Longitude column name in the CTE

    Usage (inside a CTE chain):
      with_zip AS (
          {{ spatial_zip_join('deduped', 'latitude', 'longitude') }}
      )

    Reference:
      - High-Level Architecture §5.3 (Spatial Join)
      - High-Level Architecture §7.4 (stg_nypd_arrests — Step 2)
#}

{% macro spatial_zip_join(cte_ref, lat_col, lon_col) %}
    {% set zcta_relation = adapter.get_relation(
        database=var('catalog_name'),
        schema='bronze',
        identifier='nyc_zcta_polygons'
    ) %}

    {% if zcta_relation is not none %}
    SELECT
        {{ cte_ref }}.*,
        COALESCE(zcta.zip_code, 'UNKNOWN')  AS zip_code,
        CASE
            WHEN zcta.zip_code IS NOT NULL THEN 'spatial'
            ELSE 'borough_fallback'
        END                                  AS zip_code_source
    FROM {{ cte_ref }}
    LEFT JOIN {{ source('bronze', 'nyc_zcta_polygons') }} AS zcta
        ON st_contains(
            zcta.polygon,
            st_point({{ cte_ref }}.{{ lon_col }}, {{ cte_ref }}.{{ lat_col }})
        )
    {% else %}
    SELECT
        {{ cte_ref }}.*,
        'UNKNOWN'              AS zip_code,
        'borough_fallback'     AS zip_code_source
    FROM {{ cte_ref }}
    {% endif %}
{% endmacro %}
