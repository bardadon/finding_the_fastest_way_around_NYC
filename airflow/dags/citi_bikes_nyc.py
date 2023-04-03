from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.decorators import task

from dateutil.relativedelta import relativedelta
from google.cloud import storage, bigquery
from datetime import datetime
import os


# Set default arguments
default_args = {
    'start_date': datetime(2022,1,1),
    'schedule_interval': '0 0 1 * *' # every first day of the month
    }

# Grab date to download
def grab_latest_date():

    # Access bucket
    client = storage.Client()
    bucket = client.get_bucket('citi_bikes_airflow_project')
    blobs = bucket.list_blobs()
    latest_date = datetime(2022,1,1)

    # Return 202201 for the first run of the DAG
    if blobs.num_results == 0:
        return latest_date.strftime('%Y%m')

    # Loop through blobs to find the latest date
    for blob in blobs:
        if blob.name.endswith('.zip'):
            date = blob.name.split('-')[0]
            date = datetime.strptime(date, '%Y%m')
            if date > latest_date:
                latest_date = date
    
    # Adding one month to the latest date to get the next month
    latest_date = latest_date.strftime('%Y%m')
    latest_date = datetime.strptime(latest_date, '%Y%m')
    latest_date = latest_date + relativedelta(months=1)
    return latest_date.strftime('%Y%m')

date_to_download = grab_latest_date()

# Set environment variables
AIRFLOW_HOME = '/opt/airflow'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = f'{AIRFLOW_HOME}/dags/credentials.json'

# Load data to google bucket(dag #2)
def _load_data_to_google_bucket(bucket_name, file_name):
    client = storage.Client()
    bucket = client.get_bucket(bucket_name)
    print("Bucket name: ", bucket.name)
    print(f'GOOGLE_APPLICATION_CREDENTIALS: {os.environ["GOOGLE_APPLICATION_CREDENTIALS"]}')
    bucket.blob(file_name).upload_from_filename(f'{AIRFLOW_HOME}/dags/data/{file_name}', content_type='application/zip')
    print(f'{date_to_download}-citibike-tripdata.csv.zip uploaded to Google Bucket')

# Load data to BigQuery(dag #4)
def _load_data_to_bigquery():
    bigquery_client = bigquery.Client()
    dataset_id = 'amplified-bee-376217.citi_bikes_nyc'
    table_name = 'bikes_data'
    full_id = dataset_id + '.' + table_name
    job_config = bigquery.LoadJobConfig(
        schema=[
            bigquery.SchemaField("ride_id", bigquery.enums.SqlTypeNames.STRING),
            bigquery.SchemaField("rideable_type", bigquery.enums.SqlTypeNames.STRING),
            bigquery.SchemaField("started_at", bigquery.enums.SqlTypeNames.STRING),
            bigquery.SchemaField("ended_at", bigquery.enums.SqlTypeNames.STRING),
            bigquery.SchemaField("start_station_name", bigquery.enums.SqlTypeNames.STRING),
            bigquery.SchemaField("start_station_id", bigquery.enums.SqlTypeNames.STRING),
            bigquery.SchemaField("end_station_name", bigquery.enums.SqlTypeNames.STRING),
            bigquery.SchemaField("end_station_id", bigquery.enums.SqlTypeNames.STRING),
            bigquery.SchemaField("start_lat", bigquery.enums.SqlTypeNames.FLOAT64),
            bigquery.SchemaField("start_lng", bigquery.enums.SqlTypeNames.FLOAT64),
            bigquery.SchemaField("end_lat", bigquery.enums.SqlTypeNames.FLOAT64),
            bigquery.SchemaField("end_lng", bigquery.enums.SqlTypeNames.FLOAT64),
            bigquery.SchemaField("member_casual", bigquery.enums.SqlTypeNames.STRING),
        ],
        skip_leading_rows=1,
        source_format=bigquery.SourceFormat.CSV,
    )
    with open(f'{AIRFLOW_HOME}/dags/data/{date_to_download}-citibike-tripdata.csv', "rb") as source_file:
        job = bigquery_client.load_table_from_file(source_file, full_id, job_config=job_config) # Make an API request.
        job.result()  # Waits for the job to complete.
    print(f'Loaded {job.output_rows} rows into {full_id}.')
    destination_table = bigquery_client.get_table(full_id)  # Make an API request.
    print("Loaded {} rows.".format(destination_table.num_rows))


            
# Create DAG
with DAG(dag_id='citi_bikes_nyc', default_args = default_args, catchup=True) as dag:


    # Dag #1 - download citi bike data
    download_citi_bike_data = BashOperator(
        task_id='download_citi_bike_data',
        bash_command=f'curl -o {AIRFLOW_HOME}/dags/data/{date_to_download}-citibike-tripdata.csv.zip https://s3.amazonaws.com/tripdata/{date_to_download}-citibike-tripdata.csv.zip'
    )

    # Dag #2 - Load data to Google Bucket
    @task
    def load_data_to_google_bucket(bucket_name, file_name):
        _load_data_to_google_bucket(bucket_name, file_name)

    # Dag #3 - unzip data
    unzip_data = BashOperator(
        task_id='unzip_data',
        bash_command=f'''
            cd /opt/airflow/dags/data
            unzip -o {date_to_download}-citibike-tripdata.csv.zip
        '''
    )

    # Dag #4 - Load data to BigQuery
    @task
    def load_data_to_bigquery():
        _load_data_to_bigquery()

    # Dependencies
    bucket_name = 'citi_bikes_airflow_project'
    file_name = f'{date_to_download}-citibike-tripdata.csv.zip'
    download_citi_bike_data >> load_data_to_google_bucket(bucket_name, file_name) >> unzip_data >> load_data_to_bigquery()