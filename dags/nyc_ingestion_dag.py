from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.utils.task_group import TaskGroup
from datetime import datetime, timedelta
import json
import os
import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import s3fs
import time
from urllib.parse import urlencode

# ---------------------------------------------------------------------------
# NOTE ON DATABRICKS TASKS
# ---------------------------------------------------------------------------
# Tasks that trigger Databricks notebooks use DatabricksRunNowOperator.
# The job_id for each notebook must be registered in Airflow Variables:
#
#   Variable name                   | Databricks Job to register
#   --------------------------------|-----------------------------------
#   databricks_job_id_autoloader    | Bronze loader notebooks (all 4 in one job with 4 tasks)
#   databricks_job_id_zcta_loader   | scripts/bronze/load_zcta_polygons.py
#   databricks_job_id_duckdb_export | scripts/export/export_gold_to_duckdb.py
#
# How to set up:
#   1. In Databricks, create a Job for each notebook listed above.
#   2. Note the Job ID (visible in the Databricks Jobs UI URL).
#   3. In the Airflow UI → Admin → Variables, set:
#        databricks_job_id_autoloader    = <your_job_id>
#        databricks_job_id_zcta_loader   = <your_job_id>
#        databricks_job_id_duckdb_export = <your_job_id>
#
# The Airflow Databricks connection (conn_id='databricks_default') must be
# configured with your workspace URL and a personal access token or service
# principal credentials (Admin → Connections in Airflow UI).
#
# dbt BashOperator tasks assume:
#   - dbt-databricks is installed in the Airflow worker container
#   - A profiles.yml is at $DBT_PROFILES_DIR or ~/.dbt/profiles.yml
#   - DBT_PROJECT_DIR env var points to the dbt project root
# ---------------------------------------------------------------------------

try:
    from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator
    DATABRICKS_PROVIDER_AVAILABLE = True
except ImportError:
    DATABRICKS_PROVIDER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

S3_BUCKET  = 'nyc-lakehouse-store'
PAGE_LIMIT  = 50000
MAX_BATCHES = 2

DBT_PROJECT_DIR = os.environ.get(
    'DBT_PROJECT_DIR',
    '/opt/airflow/dbt/nyc_lakehouse_dbt'
)

DATASETS = {
    '311': {
        'endpoint':          'https://data.cityofnewyork.us/resource/erm2-nwe9.json',
        'date_col':          'created_date',
        'pk_cols':           ['unique_key'],
        'default_watermark': '2020-01-01T00:00:00.000',
    },
    'nypd_historic': {
        'endpoint':          'https://data.cityofnewyork.us/resource/8h9b-rp9u.json',
        'date_col':          'arrest_date',
        'pk_cols':           ['arrest_key'],
        'default_watermark': '2006-01-01T00:00:00.000',
    },
    'nypd_ytd': {
        'endpoint':          'https://data.cityofnewyork.us/resource/uip8-fykc.json',
        'date_col':          'arrest_date',
        'pk_cols':           ['arrest_key'],
        'default_watermark': None,  # resolved dynamically to Jan 1 of current year
    },
    'dob': {
        'endpoint':          'https://data.cityofnewyork.us/resource/ipu4-2q9a.json',
        'date_col':          'issuance_date',
        'pk_cols':           ['job__', 'permit_sequence__'],
        'default_watermark': '2020-01-01T00:00:00.000',
    },
    'restaurant': {
        'endpoint':          'https://data.cityofnewyork.us/resource/43nn-pn8j.json',
        'date_col':          'inspection_date',
        'pk_cols':           ['camis', 'violation_code', 'inspection_type'],
        'default_watermark': '2015-01-01T00:00:00.000',
    },
}

default_args = {
    'owner':             'data_engineering',
    'depends_on_past':   False,
    'email_on_failure':  False,
    'email_on_retry':    False,
    'retries':           3,
    'retry_delay':       timedelta(minutes=5),
}

# ---------------------------------------------------------------------------
# Ingestion helpers (unchanged from original)
# ---------------------------------------------------------------------------

def _default_watermark_for_dataset(dataset_name, config):
    configured = config.get('default_watermark')
    if configured is not None:
        return configured
    if dataset_name == 'nypd_ytd':
        return f"{datetime.utcnow().year}-01-01T00:00:00.000"
    raise ValueError(f"No default watermark configured for dataset '{dataset_name}'")


def _escape_soql(value):
    return str(value).replace("'", "''")


def _parse_watermark(raw_value, default_date):
    """
    Supports JSON cursor {"date": "...", "pk": [...]} and legacy plain date strings.
    """
    if raw_value is None:
        return {'date': default_date, 'pk': None}
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if stripped.startswith('{'):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict) and 'date' in parsed:
                    pk = parsed.get('pk')
                    if pk is not None and not isinstance(pk, list):
                        pk = [pk]
                    return {'date': parsed['date'], 'pk': pk}
            except json.JSONDecodeError:
                pass
        return {'date': stripped, 'pk': None}
    return {'date': default_date, 'pk': None}


def _build_where_clause(date_col, pk_cols, cursor):
    """Keyset (seek) pagination predicate — no $offset."""
    date_val = _escape_soql(cursor['date'])
    pk_vals  = cursor.get('pk')

    if not pk_vals:
        return f"{date_col} > '{date_val}'"

    pk_vals = [_escape_soql(v) for v in pk_vals]

    clauses = [f"{date_col} > '{date_val}'"]
    for i in range(len(pk_cols)):
        prefix_eq = ' AND '.join(
            [f"{date_col} = '{date_val}'"]
            + [f"{pk_cols[j]} = '{pk_vals[j]}'" for j in range(i)]
        )
        clauses.append(f"({prefix_eq} AND {pk_cols[i]} > '{pk_vals[i]}')")

    return ' OR '.join(f'({c})' for c in clauses)


def _cursor_from_row(row, date_col, pk_cols):
    pk = []
    for col in pk_cols:
        if col not in row or row[col] is None:
            raise ValueError(
                f"Primary key column '{col}' missing or null in API row — "
                "cannot advance keyset cursor safely."
            )
        pk.append(str(row[col]))
    return {'date': str(row[date_col]), 'pk': pk}


def _fetch_page(url, headers, max_retries=5):
    """GET with exponential backoff on HTTP 429 (Socrata rate limit)."""
    last_response = None
    for attempt in range(max_retries):
        response      = requests.get(url, headers=headers, timeout=120)
        last_response = response
        if response.status_code == 429:
            wait = min(2 ** attempt * 2, 60)
            print(f"Rate limited (429). Retrying in {wait}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()
    last_response.raise_for_status()


def ingest_dataset(dataset_name, config, **kwargs):
    endpoint     = config['endpoint']
    date_col     = config['date_col']
    pk_cols      = config['pk_cols']
    default_date = _default_watermark_for_dataset(dataset_name, config)

    var_name      = f'watermark_{dataset_name}'
    raw_watermark = Variable.get(var_name, default_var=default_date)
    cursor        = _parse_watermark(raw_watermark, default_date)

    print(f"Starting ingestion for {dataset_name} from cursor: {cursor}")

    headers   = {'Accept': 'application/json'}
    app_token = os.environ.get('SOCRATA_APP_TOKEN')
    if app_token:
        headers['X-App-Token'] = app_token
    else:
        print(
            "[WARN] SOCRATA_APP_TOKEN not set — anonymous API access may be throttled. "
            "Add SOCRATA_APP_TOKEN to your .env file."
        )

    all_rows       = []
    batches        = 0
    last_page_full = False

    while True:
        where_clause  = _build_where_clause(date_col, pk_cols, cursor)
        order_clause  = ', '.join([date_col] + pk_cols) + ' ASC'
        query_params  = {'$where': where_clause, '$order': order_clause, '$limit': PAGE_LIMIT}
        query_url     = f"{endpoint}?{urlencode(query_params)}"
        print(f"Fetching: {query_url}")

        data = _fetch_page(query_url, headers)
        if not data:
            break

        all_rows.extend(data)
        print(f"Fetched {len(data)} rows. Total: {len(all_rows)}")

        last_row = data[-1]
        if date_col not in last_row:
            raise ValueError(f"Watermark column '{date_col}' missing from API response — aborting.")
        cursor = _cursor_from_row(last_row, date_col, pk_cols)

        last_page_full = len(data) >= PAGE_LIMIT
        if not last_page_full:
            break

        batches += 1
        if batches >= MAX_BATCHES:
            print(f"Reached max batches ({MAX_BATCHES}). Resuming via keyset on next run.")
            break

    if not all_rows:
        print(f"No new data for {dataset_name}.")
        return "No new data"

    df        = pd.DataFrame(all_rows).astype(str)
    timestamp = int(time.time())
    s3_path   = f"s3://{S3_BUCKET}/raw/{dataset_name}/{timestamp}.parquet"

    print(f"Writing {len(df)} rows to {s3_path} ...")
    pq.write_table(pa.Table.from_pandas(df), s3_path, filesystem=s3fs.S3FileSystem())
    print("S3 write successful.")

    # Advance cursor ONLY after confirmed S3 write
    Variable.set(var_name, json.dumps(cursor))
    print(f"Updated watermark {var_name} → {json.dumps(cursor)}")

    return f"Ingested {len(df)} rows."


# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------

with DAG(
    'nyc_daily_pipeline',
    default_args=default_args,
    description='End-to-end NYC Lakehouse pipeline: ingest → Bronze → dbt → DuckDB export',
    schedule_interval='@daily',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['nyc-lakehouse', 'ingestion', 'dbt', 'bronze', 'gold'],
) as dag:

    # ── Group 1: Parallel ingestion (5 datasets) ──────────────────────────
    with TaskGroup('ingest', tooltip='Socrata API → S3 Parquet (keyset pagination)') as ingest_group:
        ingest_tasks = {}
        for dataset_name, config in DATASETS.items():
            ingest_tasks[dataset_name] = PythonOperator(
                task_id=f'ingest_{dataset_name}',
                python_callable=ingest_dataset,
                op_kwargs={'dataset_name': dataset_name, 'config': config},
            )

    # ── Task: ZCTA polygon loader (idempotent — skips if already loaded) ──
    # Runs every day but exits early when table is already populated.
    # This means the ZCTA table self-heals if it's ever accidentally dropped.
    if DATABRICKS_PROVIDER_AVAILABLE:
        load_zcta = DatabricksRunNowOperator(
            task_id='load_zcta_polygons',
            databricks_conn_id='databricks_default',
            job_id=Variable.get('databricks_job_id_zcta_loader', default_var='0'),
            # ponytail: job_id=0 is an invalid Databricks job ID — the task will
            # fail visibly rather than silently doing nothing. Set the Variable in
            # Airflow UI (Admin → Variables → databricks_job_id_zcta_loader).
        )
    else:
        load_zcta = BashOperator(
            task_id='load_zcta_polygons',
            bash_command='echo "[SKIP] DatabricksRunNowOperator not available — install apache-airflow-providers-databricks"',
        )

    # ── Task: Autoloader — S3 Parquet → Bronze Delta ──────────────────────
    if DATABRICKS_PROVIDER_AVAILABLE:
        trigger_autoloader = DatabricksRunNowOperator(
            task_id='trigger_autoloader',
            databricks_conn_id='databricks_default',
            job_id=Variable.get('databricks_job_id_autoloader', default_var='0'),
        )
    else:
        trigger_autoloader = BashOperator(
            task_id='trigger_autoloader',
            bash_command='echo "[SKIP] Set databricks_job_id_autoloader in Airflow Variables"',
        )

    # ── Group 2: dbt transformation pipeline ──────────────────────────────
    with TaskGroup('dbt', tooltip='dbt run: staging → intermediate → snapshots → marts → tests') as dbt_group:

        dbt_staging = BashOperator(
            task_id='run_staging',
            bash_command=f'cd {DBT_PROJECT_DIR} && dbt run --select staging',
        )

        dbt_intermediate = BashOperator(
            task_id='run_intermediate',
            bash_command=f'cd {DBT_PROJECT_DIR} && dbt run --select intermediate',
        )

        # Snapshot runs after staging (reads from Silver) but before marts
        # (mart_food_compliance joins dim_restaurant_scd2)
        dbt_snapshots = BashOperator(
            task_id='run_snapshots',
            bash_command=f'cd {DBT_PROJECT_DIR} && dbt snapshot',
        )

        dbt_marts = BashOperator(
            task_id='run_marts',
            bash_command=f'cd {DBT_PROJECT_DIR} && dbt run --select marts',
        )

        dbt_tests = BashOperator(
            task_id='run_tests',
            bash_command=f'cd {DBT_PROJECT_DIR} && dbt test',
        )

        # dbt internal dependency order
        dbt_staging >> dbt_intermediate >> dbt_snapshots >> dbt_marts >> dbt_tests

    # ── Task: Export Gold marts → DuckDB file → S3 ────────────────────────
    if DATABRICKS_PROVIDER_AVAILABLE:
        export_duckdb = DatabricksRunNowOperator(
            task_id='export_gold_to_duckdb',
            databricks_conn_id='databricks_default',
            job_id=Variable.get('databricks_job_id_duckdb_export', default_var='0'),
        )
    else:
        export_duckdb = BashOperator(
            task_id='export_gold_to_duckdb',
            bash_command='echo "[SKIP] Set databricks_job_id_duckdb_export in Airflow Variables"',
        )

    # ── Task: Notify success ───────────────────────────────────────────────
    notify_success = PythonOperator(
        task_id='notify_success',
        python_callable=lambda **kw: print(
            f"[SUCCESS] NYC Daily Pipeline complete — "
            f"logical_date={kw.get('logical_date')} | "
            f"gold_latest.duckdb updated on S3."
        ),
        trigger_rule='all_success',
    )

    # ── Task: Notify failure (runs when any upstream task fails) ───────────
    notify_failure = PythonOperator(
        task_id='notify_failure',
        python_callable=lambda **kw: print(
            f"[FAILURE] NYC Daily Pipeline failed — check task logs. "
            f"logical_date={kw.get('logical_date')}"
        ),
        trigger_rule='one_failed',
    )

    # ── Pipeline topology ──────────────────────────────────────────────────
    #
    #  ingest_group (parallel) ──┐
    #                            ├──► load_zcta ──► trigger_autoloader ──► dbt_group ──► export_duckdb ──► notify_success
    #                            │                                                                      └──► notify_failure
    #  (all ingest tasks must    │
    #   succeed before Bronze)   │
    #                            ┘
    #
    # load_zcta runs in parallel with ingest — it downloads from NYC Open Data
    # independently, not from the S3 files that ingest produces.
    # trigger_autoloader waits for BOTH ingest_group AND load_zcta to succeed.

    [ingest_group, load_zcta] >> trigger_autoloader >> dbt_group >> export_duckdb >> [notify_success, notify_failure]
