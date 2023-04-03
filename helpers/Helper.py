from datetime import datetime
from google.cloud import storage, bigquery
import os
from dateutil.relativedelta import relativedelta

AIRFLOW_HOME = '/projects/airflow_finding_the_fastest_way_around_NYC/airflow'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = f'{AIRFLOW_HOME}/dags/credentials.json'

def create_bigquery_table():
    bigquery_client = bigquery.Client()
    dataset_id = 'amplified-bee-376217.citi_bikes_nyc'
    table_name = 'bikes_data'
    full_id = dataset_id + '.' + table_name
    bigquery_client.create_table(full_id)

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

if __name__ == '__main__':
    #create_bigquery_table()
    print(grab_latest_date())