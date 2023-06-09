#!/bin/bash

### Clean up Environment ###

if [ "$1" == "--clean-up" ]; then

    # Remove airflow folder
    rm -r $(pwd)/airflow

    # Stop and remove all containers
    docker stop $(docker ps -a -q)
    docker rm $(docker ps -a -q)

    # Remove all containers, volumes and images related to the environment
    #docker-compose down --volumes --rmi all

    # Remove all process listening to port 8080
    lsof -i tcp:8080 | grep root | awk '{print $2}' | xargs kill -9
fi

### Install Airflow locally ###

# Set Airflow's home
mkdir $(pwd)/airflow
export AIRFLOW_HOME=$(pwd)/airflow

# Create airflow folders
mkdir -p ${AIRFLOW_HOME}/dags/data

# Set airflow and python version 
AIRFLOW_VERSION=2.5.0
PYTHON_VERSION="$(python3 --version | cut -d " " -f 2 | cut -d "." -f 1-2)"

# pipe install airflow based on the constaints file
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT_URL}"

### Deploy Airflow using docker-compose ###

# Move to airflow folder
cd airflow

# fetch the docker-compose.yaml and Dockerfile
curl -LfO https://raw.githubusercontent.com/bardadon/finding_the_fastest_way_around_NYC/master/airflow/docker-compose.yaml  
curl -LfO https://raw.githubusercontent.com/bardadon/finding_the_fastest_way_around_NYC/master/airflow/Dockerfile
curl -LfO 'https://airflow.apache.org/docs/apache-airflow/2.5.0/airflow.sh'
chmod +x airflow.sh

# Create an empty .env file
> .env

# Add an airflow user id to the file
echo AIRFLOW_UID=50000 >> .env
echo PYTHONPATH=$(pwd) >> .env

export PYTHONPATH=$(pwd)

# Start airflow
docker-compose build
