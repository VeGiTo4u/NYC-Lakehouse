{#
    standardize_borough(column_name)
    
    Converts all borough formats across 4 NYC datasets into a single
    canonical UPPERCASE full name. Returns NULL for unknown/unspecified values.
    
    Formats handled:
      - 311 / DOB:    MANHATTAN, BRONX, BROOKLYN, QUEENS, STATEN ISLAND
      - NYPD:         M, B, K, Q, S
      - DOB numeric:  1, 2, 3, 4, 5
      - Restaurant:   Manhattan, Bronx, Brooklyn, Queens, Staten Island
      - Edge cases:   'Unspecified', '', NULL → NULL

    Usage:
      {{ standardize_borough('borough') }}       → for 311 / DOB
      {{ standardize_borough('arrest_boro') }}   → for NYPD
      {{ standardize_borough('boro') }}          → for Restaurant

    Reference:
      - High-Level Architecture §13 (Borough Standardisation Problem)
      - NYC_Dataset_Analysis §7 (Borough Standardisation Confirmed)
#}

{% macro standardize_borough(column_name) %}
    CASE UPPER(TRIM(CAST({{ column_name }} AS STRING)))
        -- Full uppercase names (311 / DOB / normalised Restaurant)
        WHEN 'MANHATTAN'      THEN 'MANHATTAN'
        WHEN 'BRONX'          THEN 'BRONX'
        WHEN 'BROOKLYN'       THEN 'BROOKLYN'
        WHEN 'QUEENS'         THEN 'QUEENS'
        WHEN 'STATEN ISLAND'  THEN 'STATEN ISLAND'
        WHEN 'STATEN IS'      THEN 'STATEN ISLAND'

        -- NYPD single-letter codes
        WHEN 'M' THEN 'MANHATTAN'
        WHEN 'B' THEN 'BRONX'
        WHEN 'K' THEN 'BROOKLYN'
        WHEN 'Q' THEN 'QUEENS'
        WHEN 'S' THEN 'STATEN ISLAND'

        -- DOB numeric codes
        WHEN '1' THEN 'MANHATTAN'
        WHEN '2' THEN 'BRONX'
        WHEN '3' THEN 'BROOKLYN'
        WHEN '4' THEN 'QUEENS'
        WHEN '5' THEN 'STATEN ISLAND'

        -- Null / Unknown / Unspecified
        WHEN 'UNSPECIFIED' THEN NULL
        WHEN ''            THEN NULL
        ELSE NULL
    END
{% endmacro %}
