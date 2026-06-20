{#
    generate_schema_name

    Override dbt's default schema-naming behavior.

    Default dbt behavior: <target_schema>_<custom_schema>
      (e.g. silver_gold when target=silver, config schema=gold)

    This override: use the custom schema directly when specified,
      otherwise fall back to the target schema.

    Result:
      - schema='gold'  → gold   (dim/fact tables)
      - schema='marts' → marts  (analytics mart tables)
      - no schema set  → silver (staging/intermediate — the target default)

    References:
      - dbt docs: https://docs.getdbt.com/docs/build/custom-schemas
#}

{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}
