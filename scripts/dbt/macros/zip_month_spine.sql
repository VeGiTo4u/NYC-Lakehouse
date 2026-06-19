{#
    zip_month_spine()

    Generates a Cartesian product of all distinct zip codes × all months
    from the dimension tables. Used by fact_neighborhood_monthly to ensure
    every zip code has a row for every month — even months with zero activity.

    This prevents NULL neighborhood_pulse_score values for quiet zip codes
    and ensures the Streamlit dashboard always has a complete grid to display.

    Returns columns: zip_code, year_month, borough

    Usage:
      WITH spine AS (
          {{ zip_month_spine() }}
      )

    References:
      - High-Level Architecture §14 (dbt Macros — zip_month_spine)
      - High-Level Architecture §7.6 (NULL safety required)
#}

{% macro zip_month_spine() %}

    SELECT
        z.zip_code,
        z.borough,
        d.year_month
    FROM {{ ref('dim_zip_codes') }} z
    CROSS JOIN {{ ref('dim_date') }} d

{% endmacro %}
