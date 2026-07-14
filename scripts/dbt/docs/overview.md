{% docs __overview__ %}

# NYC Neighborhood Pulse — dbt Project

## What This Project Does

This dbt project transforms raw NYC Open Data (311, NYPD, DOB, Restaurant Inspections)
from a Bronze Delta lakehouse into a curated Gold layer that powers the
**Neighborhood Pulse Score** — a composite health metric for every NYC zip code.

The Gold layer is exported as a single DuckDB file (`gold_latest.duckdb`) that
Streamlit loads once at startup for instant, zero-cost in-memory querying.

---

## Medallion Architecture

```
Bronze (Delta, append-only)
  └─► Silver/Staging    — dedup, type-cast, spatial join, borough standardisation
        └─► Silver/Intermediate — zip+month aggregations per domain
              └─► Gold/Core     — dim tables + fact_neighborhood_monthly
                    └─► Gold/Marts — analytics-ready wide tables for Streamlit
```

---

## Layers

### Bronze (source)
Append-only Delta tables. No deduplication at this layer.

| Source | Socrata ID | Watermark |
|--------|-----------|-----------|
| 311 Service Requests | erm2-nwe9 | `created_date` |
| NYPD Arrests Historic | 8h9b-rp9u | `arrest_date` |
| NYPD Arrests YTD | uip8-fykc | `arrest_date` |
| DOB Permits | ipu4-2q9a | `issuance_date` |
| Restaurant Inspections | 43nn-pn8j | `inspection_date` |
| ZCTA Polygons | NYC DCP | static |

### Silver — Staging
One model per source. Each staging model:
- Deduplicates via `QUALIFY ROW_NUMBER() OVER (PARTITION BY pk ORDER BY _ingested_at DESC) = 1`
- Casts types, standardises borough names via `{{ standardize_borough() }}`
- `stg_nypd_arrests` additionally resolves lat/lon → zip via `st_contains` on ZCTA polygons

### Silver — Intermediate
One model per domain, aggregated to `zip_code + year_month` grain.
Plus one cross-domain model:

| Model | Sources | Purpose |
|-------|---------|---------|
| `int_311_by_zip_month` | stg_311_requests | Complaint counts + resolution metrics |
| `int_arrests_by_zip_month` | stg_nypd_arrests | Arrest counts by severity |
| `int_permits_by_zip_month` | stg_dob_permits | Permit counts by job type |
| `int_inspections_by_zip_month` | stg_restaurant_inspections | Inspection scores + grade pcts |
| `int_complaint_permit_corr` | int_311 + int_permits | Construction ↔ noise correlation (Q16) |

### Gold — Core (Star Schema)
| Model | Type | Purpose |
|-------|------|---------|
| `dim_zip_codes` | table | Zip code attributes — seed + staging fallback |
| `dim_date` | table | Calendar dimension (month grain) |
| `dim_complaint_types` | table | 311 complaint type reference |
| `dim_permit_types` | table | DOB permit type reference |
| `fact_neighborhood_monthly` | incremental | One row per zip per month — all 4 domains |

### Gold — Analytics Marts
| Model | Purpose |
|-------|---------|
| `mart_neighborhood_pulse` | Denormalized wide table — primary Streamlit source |
| `mart_safety_infrastructure_corr` | Arrest × permit correlation |
| `mart_top_complaints_by_borough` | Complaint type ranking by borough+month |
| `mart_food_compliance` | Food complaint ↔ inspection score cross-domain |

### Snapshots
| Snapshot | Purpose |
|----------|---------|
| `restaurant_grade_snapshot` | SCD2 history of restaurant grade changes |

---

## Neighborhood Pulse Score

The central KPI. Composite of four weighted factors (0–100, higher = healthier):

```
score = (100 - LEAST(complaints / 100, 100)) * 0.25   -- complaint pressure
      + (100 - LEAST(arrests / 50, 100))     * 0.25   -- safety
      + (100 - LEAST(active_permits / 20, 100)) * 0.20  -- construction disruption
      + (pct_grade_a * 100)                  * 0.30   -- food safety
```

Computed in `fact_neighborhood_monthly`. All inputs are `COALESCE`-guarded.
`avg_resolution_hours` is intentionally **not** in the formula and is left NULL
when no complaints were closed (not COALESCE(0) — that would imply instant resolution).

---

## Incremental Strategy

All staging and intermediate models use `incremental_strategy='merge'` with a
**lookback window** to handle late-arriving data:

- Default lookback: 90 days (`var('lookback_days_default')`)
- NYPD lookback: 200 days (`var('lookback_days_nypd')`) — NYPD releases historic data quarterly

Watermarks are managed as Airflow Variables (JSON cursors) — not Delta tables.

---

## Key Macros

| Macro | Purpose |
|-------|---------|
| `standardize_borough` | Normalises any borough format (M/Mnhtn/Manhattan) → `MANHATTAN` |
| `zip_month_spine` | Cartesian product dim_zip_codes × dim_date for the fact table |
| `safe_divide` | NULL-safe division (returns NULL when denominator = 0) |
| `generate_schema_name` | Routes models to correct schema (silver/gold/marts) |
| `generate_staging_audit_cols` | Consistent audit columns for all staging models |
| `generate_gold_audit_cols` | Consistent audit columns for all Gold models |

---

## Analyses

Ad-hoc SQL in `analyses/` — compiled by dbt but never materialised:

- **`complaint_permit_lag_analysis.sql`** — Answers Q16: does construction activity
  in month T predict noise complaints in T+1 or T+2? Self-joins
  `int_complaint_permit_corr` with 1- and 2-month offsets. Run the compiled
  SQL in a Databricks notebook to compute Pearson correlation.

---

## Running This Project

```bash
# Install packages
dbt deps

# Seed reference data
dbt seed

# Full first run
dbt run

# Run tests
dbt test

# Check source freshness
dbt source freshness

# Generate + view docs
dbt docs generate && dbt docs serve

# Incremental update (daily pipeline — triggered by Airflow)
dbt run --select staging intermediate marts
dbt snapshot
dbt test
```

{% enddocs %}
