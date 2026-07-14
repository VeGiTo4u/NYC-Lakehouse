# Databricks notebook source

# ============================================================
# Bronze Loader: NYC ZCTA Polygons (One-Time / Idempotent)
#
# Loads the NYC Zip Code Tabulation Area (ZCTA) shapefile into
# bronze.nyc_zcta_polygons as a static Delta table.
#
# This table is the spatial reference used by stg_nypd_arrests
# to resolve arrest lat/lon to a single exact zip code via
# st_contains() (point-in-polygon). Without it, ALL arrests
# get zip_code = 'UNKNOWN'.
#
# Source  : NYC Department of City Planning ZCTA GeoJSON
#           https://data.cityofnewyork.us/resource/pri4-ifjk.geojson
#           (NYC Open Data -- public, no auth required)
# Target  : {catalog}.bronze.nyc_zcta_polygons
# Grain   : one row per ZCTA (zip code)
# Mode    : OVERWRITE on every run (idempotent -- static reference data)
#
# Run cadence: Once when pipeline is first set up, or whenever
#              the ZCTA shapefile is updated by NYC DCP (~yearly).
#
# Architecture Reference:
#   High-Level Architecture.md -- Section 5.3 (NYPD Spatial Join)
#   High-Level Architecture.md -- Section 7.3 (bronze.nyc_zcta_polygons)
# ============================================================

# COMMAND ----------

%run /Workspace/NYC-Lakehouse/scripts/bronze/utils

# COMMAND ----------

# -- Widgets -----------------------------------------------

dbutils.widgets.text("catalog", "nyc-lakehouse", "Catalog Name")
dbutils.widgets.text("schema", "bronze", "Schema Name")
dbutils.widgets.text(
    "zcta_geojson_url",
    "https://data.cityofnewyork.us/resource/pri4-ifjk.geojson?$limit=300",
    "ZCTA GeoJSON URL",
)
dbutils.widgets.text(
    "s3_target_path",
    "s3://nyc-lakehouse-store/bronze/nyc_zcta_polygons/",
    "S3 Delta Location",
)

catalog          = dbutils.widgets.get("catalog")
schema           = dbutils.widgets.get("schema")
zcta_geojson_url = dbutils.widgets.get("zcta_geojson_url")
s3_target_path   = dbutils.widgets.get("s3_target_path")

full_table_name  = f"`{catalog}`.`{schema}`.`nyc_zcta_polygons`"

# COMMAND ----------

# -- Idempotency check -------------------------------------
# Skip the download+load if the table already has rows.
# Re-run only needed when NYC DCP updates the ZCTA boundaries (~yearly).

try:
    existing_count = spark.table(full_table_name).count()
    if existing_count > 0:
        print(f"[INFO] {full_table_name} already has {existing_count} rows -- skipping load.")
        dbutils.notebook.exit(f"SKIPPED: table already populated ({existing_count} rows)")
except Exception:
    print(f"[INFO] {full_table_name} does not exist yet -- proceeding with load.")

# COMMAND ----------

# -- Download ZCTA GeoJSON ---------------------------------

import requests
import json

print(f"Downloading ZCTA GeoJSON from {zcta_geojson_url} ...")
response = requests.get(zcta_geojson_url, timeout=60)
response.raise_for_status()

features = response.json()
print(f"Downloaded {len(features)} ZCTA features.")

# COMMAND ----------

# -- Parse into rows ---------------------------------------
# Each feature has: modzcta (zip code) + the_geom (GeoJSON geometry)

rows = []
for feat in features:
    zip_code = str(feat.get("modzcta") or feat.get("zcta5ce10") or "").strip()
    geometry = feat.get("the_geom") or feat.get("geometry") or {}

    if not zip_code:
        print(f"[WARN] Skipping feature with no zip_code field: {feat}")
        continue

    rows.append({
        "zip_code":      zip_code,
        "geometry_json": json.dumps(geometry),   # WKT or GeoJSON string for st_geomfromgeojson
    })

print(f"Parsed {len(rows)} valid ZCTA rows (skipped {len(features) - len(rows)} with no zip_code).")

# COMMAND ----------

# -- Build Spark DataFrame with geometry column ------------
# Databricks H3 / Mosaic / built-in spatial: use st_geomfromgeojson to
# create the geometry column from the JSON string.

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

schema_def = StructType([
    StructField("zip_code",      StringType(), nullable=False),
    StructField("geometry_json", StringType(), nullable=False),
])

raw_df = spark.createDataFrame(rows, schema=schema_def)

# Convert geometry JSON string → native geometry type
# st_geomfromgeojson is available in Databricks Runtime 11+ natively
zcta_df = raw_df.withColumn(
    "polygon",
    F.expr("st_geomfromgeojson(geometry_json)")
).drop("geometry_json")

print(f"Schema after geometry parsing:")
zcta_df.printSchema()

# COMMAND ----------

# -- Write to Bronze (OVERWRITE -- static reference data) --

setup_bronze_schema(catalog, schema)

(
    zcta_df.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .option("path", s3_target_path)
    .saveAsTable(full_table_name)
)

final_count = spark.table(full_table_name).count()
print(f"[SUCCESS] Written {final_count} ZCTA rows to {full_table_name}")

# COMMAND ----------

# -- Validate geometry column is non-null ------------------

null_geom_count = spark.table(full_table_name).filter("polygon IS NULL").count()
if null_geom_count > 0:
    raise ValueError(
        f"[FAIL] {null_geom_count} rows have NULL geometry after load. "
        "Check that st_geomfromgeojson parsed the GeoJSON correctly."
    )
print(f"[OK] All {final_count} ZCTA rows have valid geometry.")

# COMMAND ----------

# -- Summary -----------------------------------------------

print(f"""
=== ZCTA Polygon Load Summary ===
Table          : {full_table_name}
S3 location    : {s3_target_path}
Rows loaded    : {final_count}
Geometry col   : polygon (st_geomfromgeojson)
Null geom rows : {null_geom_count}
Source URL     : {zcta_geojson_url}
=================================
""")
