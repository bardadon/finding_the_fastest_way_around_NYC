FROM apache/airflow:2.5.0

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        unzip \
        wget \
        vim \
        curl \
        python3-pip \
        python3-dev

COPY requirements.txt /requirements.txt

USER airflow

ENV AIRFLOW_UID=50000
ENV AIRFLOW_GID=50000
ENV AIRFLOW_HOME=/opt/airflow
ENV GOOGLE_APPLICATION_CREDENTIALS=${AIRFLOW_HOME}/dags/credentials.json

RUN pip install --no-cache-dir -r /requirements.txt

COPY dags /opt/airflow/dags
COPY tests /opt/airflow/tests
COPY plugins /opt/airflow/plugins
