FROM apache/airflow:2.5.0

USER root

ENV AIRFLOW_UID=50000
ENV AIRFLOW_GID=50000
ENV AIRFLOW_HOME=/opt/airflow
ENV GOOGLE_APPLICATION_CREDENTIALS=${AIRFLOW_HOME}/dags/credentials.json

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        unzip \
        wget \
        vim \
        curl \
        python3-pip \
        python3-dev

RUN sudo apt-get install apt-transport-https ca-certificates gnupg 
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list 
RUN curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - 
RUN sudo apt-get update && sudo apt-get install google-cloud-cli 

COPY requirements.txt ${AIRFLOW_HOME}/requirements.txt

USER airflow

RUN pip install --no-cache-dir -r ${AIRFLOW_HOME}/requirements.txt

COPY dags ${AIRFLOW_HOME}/dags
