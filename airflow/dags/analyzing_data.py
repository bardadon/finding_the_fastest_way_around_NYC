from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.decorators import task
from airflow.providers.google.cloud.operators.bigquery import BigQueryExecuteQueryOperator, BigQueryInsertJobOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.sensors.filesystem import FileSensor


from datetime import datetime
from dateutil.relativedelta import relativedelta
import os
from google.cloud import storage, bigquery
import pandas as pd
import numpy as np

# Set default arguments
default_args = {
    'start_date': datetime(2022,1,1),
    'schedule_interval': '* * * * *' # every first day of the month
}

# Set Variables
AIRFLOW_HOME = '/opt/airflow'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = f'{AIRFLOW_HOME}/dags/credentials.json'

# Google Cloud details for BigQuery(Task #2)
PROJECT = 'amplified-bee-376217'
DATASET='citi_bikes_nyc'
TBL_TO_MOVE='bikes_data'
DESTINATION_DS='citi_bikes_nyc'

#######################
### Helper functions 
# 1. grab_latest_date()
# 2. grab_number_of_rows()
# 3. grab_all_stations()
# 4. initialize_algorithm()
# 5. dijkstra()
# 6. find_shortest_path()
# 7. create_graph()
#######################

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

def grab_number_of_rows():

    # Connect to Google BigQuery
    client = bigquery.Client()

    # query the data in chunks of 100000 rows, append each query result to a list and then concatenate the list into a dataframe
    query = '''
    SELECT count(*) 
    FROM `amplified-bee-376217.citi_bikes_nyc.rides_under_hour` 
    '''

    query_job = client.query(query)
    results = query_job.result()
    number_of_rows = results.to_dataframe().iloc[0,0]

    return number_of_rows

def grab_all_stations():

    # Connect to Google BigQuery
    client = bigquery.Client()

    # Grab all unique stations from `amplified-bee-376217.citi_bikes_nyc.rides_under_hour` 
    query = '''
    SELECT DISTINCT start_station_name, end_station_name
    FROM `amplified-bee-376217.citi_bikes_nyc.rides_under_hour` 
    '''
    query_job = client.query(query)
    results = query_job.result()
    stations = results.to_dataframe()
    start_stations = stations.start_station_name.to_list()
    end_stations = stations.end_station_name.to_list()
    all_stations = list(set(start_stations).union(end_stations))

    return all_stations

def create_graph(rides_under_hour):

    graph = {}

    start_stations = rides_under_hour.start_station_name.to_list()
    end_stations = rides_under_hour.end_station_name.to_list()
    stations = list(set(start_stations).union(set(end_stations)))

    for station in stations:
        graph[station] = rides_under_hour[rides_under_hour.start_station_name == station][['end_station_name','duration_in_minutes']].set_index('end_station_name').to_dict().get("duration_in_minutes")

    return graph


def initialize_algorithm(all_stations, start_station_name):

    shortest_distance = {}

    # Initialize the shortest distance. If distance is not np.inf, then it has been visited and keep it like this
    for station in all_stations:
        if station == start_station_name:
            shortest_distance[station] = 0
        else:
            shortest_distance[station] = np.inf

    # routes dictionary to keep track of the routes
    routes = {}
    for station in all_stations:
        routes[station] = [start_station_name]

    return shortest_distance, routes

def dijkstra(routes, graph, visited, unvisited, destination_station, shortest_distance, all_stations):


    while len(visited) < len(all_stations):

        # Find the node with the shortest distance. That's the current node
        min_distance = np.inf
        for node in all_stations:
            if shortest_distance[node] < min_distance and node not in visited:
                min_distance = shortest_distance[node]
                current_node = node

        # Add node to the visited list and remove from unvisited.
        visited.append(current_node)
        

        # If the current node is the destination, then we are done  
        if current_node == destination_station:
            break

        if current_node in unvisited:
            unvisited.remove(current_node)

        # Update the shortest distance for the neighbors of the current node
        if current_node in graph:
            neighbors = graph[current_node]
        else:
            continue

        # Find the distance from the start to each neighbor of the current node
        for neigh in neighbors:
            distance_start_to_current = shortest_distance.get(current_node)
            distance_current_to_neigh = graph.get(current_node).get(neigh)
            distance_start_to_neigh = distance_start_to_current + distance_current_to_neigh

            # If the distance from start to neighbor is shortest than the current shortest distance, update distance
            if distance_start_to_neigh < shortest_distance.get(neigh):
                shortest_distance[neigh] = distance_start_to_neigh
                print(f"Found Shorter Path. Shortest Distance to {neigh}: {shortest_distance[neigh]}")

                # Update the route to the neighbor
                routes[neigh] = routes[current_node] + [neigh]

    return shortest_distance, visited, unvisited, routes

def _find_shortest_path(start_station_name, destination_station, max_rows_to_process, all_stations, chunk_size = 50000):

    # Connect to Google BigQuery
    client = bigquery.Client()

    # Initialize variables
    visited = []
    unvisited = grab_all_stations()
    shortest_distance, routes = initialize_algorithm(unvisited, start_station_name)

    # Process shortest trips in chunks
    for chunk in range(0, max_rows_to_process, chunk_size):

        if chunk % chunk_size == 0:
            print(f'{chunk} rows processed')
        
        # Stop when reaching max rows to process
        if chunk >= max_rows_to_process:
            break

        # Grab chunk of data from Google BigQuery
        query = f'''
        SELECT 
            start_station_name,
            end_station_name,
            min(duration_in_minutes) as duration_in_minutes
        FROM `amplified-bee-376217.citi_bikes_nyc.rides_under_hour`
        GROUP BY
            start_station_name,
            end_station_name
        LIMIT {chunk_size}
        OFFSET {chunk}
        '''

        # Run query and convert to dataframe
        query_job = client.query(query)
        rides_under_hour = query_job.result()
        rides_under_hour = rides_under_hour.to_dataframe()

        # Create graph
        graph = create_graph(rides_under_hour)

        # Run Dijkstra's Algorithm
        shortest_distance, visited, unvisited, routes = dijkstra(routes, graph, visited, unvisited, destination_station, shortest_distance, all_stations)

        # Clear variables
        visited = []

    # Export routes to txt
    with open(f'{AIRFLOW_HOME}/dags/data/routes_{start_station_name}_{destination_station}.txt', 'w') as f:
            f.write(f'{routes.get(destination_station)}')
    f.close()
                    
    # Export shortest_distance to CSV
    shortest_distance_df = pd.DataFrame.from_dict(shortest_distance, orient='index')
    shortest_distance_df = shortest_distance_df[shortest_distance_df.iloc[0:,0] < np.inf]
    shortest_distance_df.to_csv(f'{AIRFLOW_HOME}/dags/data/distances_{start_station_name}_{destination_station}.csv')

    # Print results
    print(f"The shortest distance from {start_station_name} to {destination_station} is: {shortest_distance.get(destination_station)} minutes")
    print(f"The shortest route from {start_station_name} to {destination_station} is: {routes.get(destination_station)}")

    return shortest_distance

with DAG(dag_id='analyzing_data', default_args=default_args, catchup=True) as dag:

    # Task #1 - Wait for data to be loaded
    check_for_data = FileSensor(
        task_id='check_for_data',
        filepath=f'{AIRFLOW_HOME}/dags/data/{date_to_download}-citibike-tripdata.csv',
        fs_conn_id='citi_bike_data_path'
    )

    # Task #2 - Create a view of relevant data
    create_view = BashOperator(
        task_id='create_view',
        bash_command=f'bq query --use_legacy_sql=false --allow_large_results=true --replace --append_table < {AIRFLOW_HOME}/dags/create_view.sql'
        )

    # Task #3 - Question 1: What are the most popular stations?
    most_popular_stations = BigQueryExecuteQueryOperator(
        task_id='most_popular_stations',
        sql=f'''
            SELECT
                start_station_name,
                COUNT(*) AS num_rides
            FROM    
                `{PROJECT}.{DATASET}.{TBL_TO_MOVE}`
            GROUP BY
                start_station_name
            ORDER BY
                num_rides DESC
        ''',    
        use_legacy_sql=False,
        gcp_conn_id='google_cloud_default',
        destination_dataset_table=f'{DESTINATION_DS}.most_popular_stations',
        write_disposition='WRITE_TRUNCATE',
        allow_large_results=True
    )

    # Task #4 - Question 2: What are the most popular routes?
    most_popular_routes = BigQueryExecuteQueryOperator(
        task_id = 'most_popular_routes',
        sql = '''
            select 
                r.start_station_name,
                r.end_station_name,
                count(*) as number_of_trips
            from 
                `citi_bikes_nyc.rides_under_hour` as r
            group by
                r.start_station_name,
                r.end_station_name
            order by 
                count(*) desc;
            ''',
        use_legacy_sql=False,
        gcp_conn_id='google_cloud_default',
        destination_dataset_table=f'{DESTINATION_DS}.most_popular_routes',
        write_disposition='WRITE_TRUNCATE',
        allow_large_results=True
    )

    # Task #5 - What is the fastest route to get to a destination station?
    @task
    def find_shortest_path(start_station_name, destination_station, max_rows_to_process, all_stations, chunk_size):
        _find_shortest_path(start_station_name = start_station_name,
                           destination_station = destination_station, 
                           max_rows_to_process = max_rows_to_process, 
                           all_stations = all_stations, 
                           chunk_size = chunk_size)
        
    # Dependencies
    number_of_rows = grab_number_of_rows()
    all_stations = grab_all_stations()
    start_station_name = 'Henry St & Grand St'
    destination_station = 'W 36 St & 9 Ave'
    max_rows_to_process = 100000
    chunk_size = 25000

    #check_for_data >> create_view >> [most_popular_stations, most_popular_routes] 
    find_shortest_path(start_station_name, destination_station, max_rows_to_process, all_stations, chunk_size)
    #[most_popular_stations, most_popular_routes] >> shortest_distance

