from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
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

# Default arguments for the DAG
default_args = {
    'owner': 'data_engineering',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=1),
}

# S3 Bucket Configuration
S3_BUCKET = 'nyc-lakehouse-store'

# Page size and per-run cap (max_batches * limit rows per DAG run)
PAGE_LIMIT = 50000
MAX_BATCHES = 2

# Dataset configurations
# pk_cols: tie-breaker columns for keyset pagination (ordered with date_col)
DATASETS = {
    '311': {
        'endpoint': 'https://data.cityofnewyork.us/resource/erm2-nwe9.json',
        'date_col': 'created_date',
        'pk_cols': ['unique_key'],
        'default_watermark': '2020-01-01T00:00:00.000',
    },
    'nypd_historic': {
        'endpoint': 'https://data.cityofnewyork.us/resource/8h9b-rp9u.json',
        'date_col': 'arrest_date',
        'pk_cols': ['arrest_key'],
        'default_watermark': '2006-01-01T00:00:00.000',
    },
    'nypd_ytd': {
        'endpoint': 'https://data.cityofnewyork.us/resource/uip8-fykc.json',
        'date_col': 'arrest_date',
        'pk_cols': ['arrest_key'],
        'default_watermark': None,  # resolved dynamically to start of current year
    },
    'dob': {
        'endpoint': 'https://data.cityofnewyork.us/resource/ipu4-2q9a.json',
        'date_col': 'issuance_date',
        'pk_cols': ['job__', 'permit_sequence__'],
        'default_watermark': '2020-01-01T00:00:00.000',
    },
    'restaurant': {
        'endpoint': 'https://data.cityofnewyork.us/resource/43nn-pn8j.json',
        'date_col': 'inspection_date',
        'pk_cols': ['camis', 'violation_code', 'inspection_type'],
        'default_watermark': '2015-01-01T00:00:00.000',
    },
}


def _default_watermark_for_dataset(dataset_name, config):
    """Return the configured default watermark, rolling nypd_ytd to Jan 1 of current year."""
    configured = config.get('default_watermark')
    if configured is not None:
        return configured
    if dataset_name == 'nypd_ytd':
        return f"{datetime.utcnow().year}-01-01T00:00:00.000"
    raise ValueError(f"No default watermark configured for dataset '{dataset_name}'")


def _escape_soql(value):
    """Escape a value for embedding in a SoQL string literal."""
    return str(value).replace("'", "''")


def _parse_watermark(raw_value, default_date):
    """
    Parse an Airflow Variable watermark.

    Supports:
      - JSON cursor: {"date": "...", "pk": ["v1", "v2"]} or {"date": "...", "pk": "v1"}
      - Legacy plain date string watermarks from earlier runs
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


def _serialize_watermark(cursor):
    return json.dumps(cursor)


def _build_order_clause(date_col, pk_cols):
    return ', '.join([date_col] + pk_cols) + ' ASC'


def _build_where_clause(date_col, pk_cols, cursor):
    """
    Keyset (seek) pagination predicate — no $offset.

    Returns rows strictly after the stored (date, pk...) cursor.
    """
    date_val = _escape_soql(cursor['date'])
    pk_vals = cursor.get('pk')

    if not pk_vals:
        return f"{date_col} > '{date_val}'"

    pk_vals = [_escape_soql(v) for v in pk_vals]

    # Lexicographic: (date, pk1, pk2, ...) > (cursor_date, cursor_pk1, ...)
    clauses = [f"{date_col} > '{date_val}'"]

    for i in range(len(pk_cols)):
        prefix_eq = ' AND '.join(
            [f"{date_col} = '{date_val}'"]
            + [f"{pk_cols[j]} = '{pk_vals[j]}'" for j in range(i)]
        )
        clauses.append(f"({prefix_eq} AND {pk_cols[i]} > '{pk_vals[i]}')")

    return ' OR '.join(f'({c})' for c in clauses)


def _cursor_from_row(row, date_col, pk_cols):
    """Build the next keyset cursor from the last row in a fetched page."""
    pk = []
    for col in pk_cols:
        if col not in row or row[col] is None:
            raise ValueError(
                f"Primary key column '{col}' missing or null in API row — "
                "cannot advance keyset cursor safely."
            )
        pk.append(str(row[col]))
    return {'date': str(row[date_col]), 'pk': pk}


def _request_headers():
    headers = {'Accept': 'application/json'}
    app_token = os.environ.get('SOCRATA_APP_TOKEN')
    if app_token:
        headers['X-App-Token'] = app_token
    return headers


def _fetch_page(url, headers, max_retries=5):
    """GET with exponential backoff on HTTP 429 (Socrata rate limit)."""
    last_response = None
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers, timeout=120)
        last_response = response

        if response.status_code == 429:
            wait_seconds = min(2 ** attempt * 2, 60)
            print(
                f"Rate limited (429). Retrying in {wait_seconds}s "
                f"(attempt {attempt + 1}/{max_retries})..."
            )
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        return response.json()

    last_response.raise_for_status()


def ingest_dataset(dataset_name, config, **kwargs):
    endpoint = config['endpoint']
    date_col = config['date_col']
    pk_cols = config['pk_cols']
    default_date = _default_watermark_for_dataset(dataset_name, config)

    var_name = f'watermark_{dataset_name}'
    raw_watermark = Variable.get(var_name, default_var=default_date)
    cursor = _parse_watermark(raw_watermark, default_date)

    print(f"Starting ingestion for {dataset_name} from cursor: {cursor}")

    headers = _request_headers()
    if 'X-App-Token' not in headers:
        print(
            "[WARN] SOCRATA_APP_TOKEN not set — anonymous API access may be throttled. "
            "Add SOCRATA_APP_TOKEN to your .env file."
        )

    all_rows = []
    batches = 0
    last_page_full = False

    while True:
        where_clause = _build_where_clause(date_col, pk_cols, cursor)
        order_clause = _build_order_clause(date_col, pk_cols)

        query_params = {
            '$where': where_clause,
            '$order': order_clause,
            '$limit': PAGE_LIMIT,
        }
        query_url = f"{endpoint}?{urlencode(query_params)}"
        print(f"Fetching from: {query_url}")

        data = _fetch_page(query_url, headers)

        if not data:
            break

        all_rows.extend(data)
        print(f"Fetched {len(data)} rows. Total so far: {len(all_rows)}")

        last_row = data[-1]
        if date_col not in last_row:
            raise ValueError(
                f"Watermark column '{date_col}' missing from API response — aborting."
            )
        cursor = _cursor_from_row(last_row, date_col, pk_cols)

        last_page_full = len(data) >= PAGE_LIMIT
        if not last_page_full:
            break

        batches += 1
        if batches >= MAX_BATCHES:
            print(
                f"Reached max batches limit ({MAX_BATCHES}). "
                "Cursor saved at last fetched row; next run will resume via keyset pagination."
            )
            break

    if not all_rows:
        print(f"No new data found for {dataset_name}.")
        return "No new data"

    df = pd.DataFrame(all_rows)

    timestamp = int(time.time())
    s3_path = f"s3://{S3_BUCKET}/raw/{dataset_name}/{timestamp}.parquet"

    print(f"Writing {len(df)} rows to {s3_path}...")

    # All columns as string — Bronze Autoloader infers STRING consistently
    df = df.astype(str)
    table = pa.Table.from_pandas(df)

    s3 = s3fs.S3FileSystem()
    pq.write_table(table, s3_path, filesystem=s3)
    print("Write to S3 successful.")

    # Advance cursor only after confirmed S3 write.
    # Keyset cursor always points at the last row written — safe for partial runs too.
    Variable.set(var_name, _serialize_watermark(cursor))
    print(f"Updated watermark {var_name} to {_serialize_watermark(cursor)}")

    return f"Successfully ingested {len(df)} rows."


with DAG(
    'nyc_incremental_ingestion',
    default_args=default_args,
    description='Incremental ingestion of NYC Open Data to S3',
    schedule_interval='*/10 * * * *',  # Every 10 minutes (dev cadence)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['ingestion', 'nyc-lakehouse-store', 'raw'],
) as dag:

    for dataset_name, config in DATASETS.items():
        PythonOperator(
            task_id=f'ingest_{dataset_name}',
            python_callable=ingest_dataset,
            op_kwargs={
                'dataset_name': dataset_name,
                'config': config,
            },
        )
