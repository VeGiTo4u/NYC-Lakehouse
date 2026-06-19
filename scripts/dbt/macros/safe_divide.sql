{#
    safe_divide(numerator, denominator, precision)

    Performs division with NULL-safety — returns NULL when the denominator
    is zero or NULL, preventing division-by-zero errors in mart models.

    Optionally rounds the result to the specified precision.

    Arguments:
      numerator   (string) — SQL expression for the numerator
      denominator (string) — SQL expression for the denominator
      precision   (int, optional) — decimal places to round to (default: no rounding)

    Usage:
      {{ safe_divide('felony_count', 'total_arrests') }}
      {{ safe_divide('felony_count', 'total_arrests', 4) }}

    References:
      - High-Level Architecture §14 (dbt Macros — safe_divide)
#}

{% macro safe_divide(numerator, denominator, precision=none) %}

    {% if precision is not none %}
        ROUND(
            CASE
                WHEN {{ denominator }} = 0 OR {{ denominator }} IS NULL THEN NULL
                ELSE CAST({{ numerator }} AS DOUBLE) / {{ denominator }}
            END,
            {{ precision }}
        )
    {% else %}
        CASE
            WHEN {{ denominator }} = 0 OR {{ denominator }} IS NULL THEN NULL
            ELSE CAST({{ numerator }} AS DOUBLE) / {{ denominator }}
        END
    {% endif %}

{% endmacro %}
