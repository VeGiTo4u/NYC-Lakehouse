from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from datetime import datetime, timedelta
import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import s3fs
import time

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

# Dataset configurations
DATASETS = {
    '311': {
        'endpoint': 'https://data.cityofnewyork.us/resource/erm2-nwe9.json',
        'date_col': 'created_date',
        'default_watermark': '2020-01-01T00:00:00.000'
    },
    'nypd_historic': {
        'endpoint': 'https://data.cityofnewyork.us/resource/8h9b-rp9u.json',
        'date_col': 'arrest_date',
        'default_watermark': '2006-01-01T00:00:00.000'
    },
    'nypd_ytd': {
        'endpoint': 'https://data.cityofnewyork.us/resource/uip8-fykc.json',
        'date_col': 'arrest_date',
        'default_watermark': '2024-01-01T00:00:00.000'
    },
    'dob': {
        'endpoint': 'https://data.cityofnewyork.us/resource/ipu4-2q9a.json',
        'date_col': 'issuance_date',
        'default_watermark': '2020-01-01T00:00:00.000'
    },
    'restaurant': {
        'endpoint': 'https://data.cityofnewyork.us/resource/43nn-pn8j.json',
        'date_col': 'inspection_date',
        'default_watermark': '2015-01-01T00:00:00.000'
    }
}

def ingest_dataset(dataset_name, config, **kwargs):
    endpoint = config['endpoint']
    date_col = config['date_col']
    default_watermark = config['default_watermark']
    
    # Read watermark from Airflow Variables
    var_name = f'watermark_{dataset_name}'
    watermark = Variable.get(var_name, default_var=default_watermark)
    
    print(f"Starting ingestion for {dataset_name} from watermark: {watermark}")
    
    limit = 50000
    offset = 0
    all_rows = []
    max_date_fetched = watermark
    batches = 0
    max_batches = 2 # Max 100,000 rows per run to prevent OOM/timeouts and extend run period
    
    while True:
        # Construct SoQL query
        query_url = f"{endpoint}?$where={date_col}>'{watermark}'&$order={date_col} ASC&$limit={limit}&$offset={offset}"
        print(f"Fetching from: {query_url}")
        
        response = requests.get(query_url)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            break
            
        all_rows.extend(data)
        print(f"Fetched {len(data)} rows. Total so far: {len(all_rows)}")
        
        # Track the maximum date fetched to update the watermark later
        for row in data:
            if date_col in row and row[date_col] > max_date_fetched:
                max_date_fetched = row[date_col]
        
        if len(data) < limit:
            break
            
        offset += limit
        batches += 1
        if batches >= max_batches:
            print(f"Reached max batches limit ({max_batches}). Stopping this run.")
            break
        
    if not all_rows:
        print(f"No new data found for {dataset_name}.")
        return "No new data"
        
    # Convert to pandas DataFrame
    df = pd.DataFrame(all_rows)
    
    # Write to S3 as Parquet
    timestamp = int(time.time())
    s3_path = f"s3://{S3_BUCKET}/raw/{dataset_name}/{timestamp}.parquet"
    
    print(f"Writing {len(df)} rows to {s3_path}...")
    
    # Convert to PyArrow Table
    # All columns as string initially since Bronze should store everything as STRING
    df = df.astype(str)
    table = pa.Table.from_pandas(df)
    
    # Write directly to S3
    s3 = s3fs.S3FileSystem() # Uses boto3 credentials implicitly
    pq.write_table(table, s3_path, filesystem=s3)
    print("Write to S3 successful.")
    
    # Update watermark variable ONLY after successful S3 write
    Variable.set(var_name, max_date_fetched)
    print(f"Updated watermark {var_name} to {max_date_fetched}")
    
    return f"Successfully ingested {len(df)} rows."


with DAG(
    'nyc_incremental_ingestion',
    default_args=default_args,
    description='Incremental ingestion of NYC Open Data to S3',
    schedule_interval='*/10 * * * *', # Every 10 minutes
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['ingestion', 'nyc-lakehouse-store', 'raw'],
) as dag:

    for dataset_name, config in DATASETS.items():
        task = PythonOperator(
            task_id=f'ingest_{dataset_name}',
            python_callable=ingest_dataset,
            op_kwargs={
                'dataset_name': dataset_name,
                'config': config
            },
        )
