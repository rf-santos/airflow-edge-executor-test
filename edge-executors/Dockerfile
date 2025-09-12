# Reusable Airflow EdgeExecutor container for Cloud Run
# - Runs a lightweight health server for Cloud Run
# - Starts an Airflow Edge worker configured via env vars

FROM apache/airflow:2.10.5-python3.12

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    AIRFLOW__CORE__LOAD_EXAMPLES=False \
    AIRFLOW__CORE__EXECUTOR=airflow.providers.edge3.executors.edge_executor.EdgeExecutor \
    EDGE_PROVIDER_VERSION=1.1.3

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy runtime scripts
COPY edge-executors/entrypoint.sh /opt/edge/entrypoint.sh
COPY edge-executors/healthz.py /opt/edge/healthz.py
RUN chmod +x /opt/edge/entrypoint.sh

USER airflow

# Pre-upgrade pydantic to satisfy provider requirement (>=2.11.0) then install provider
RUN pip install --no-cache-dir "pydantic>=2.11.0,<3" \
    && pip install --no-cache-dir apache-airflow-providers-edge3==${EDGE_PROVIDER_VERSION}

# Minimal, shared requirements for both teams (add more if needed per team at build time)
COPY edge-executors/requirements.txt /opt/edge/requirements.txt
RUN pip install --no-cache-dir -r /opt/edge/requirements.txt

ENTRYPOINT ["/opt/edge/entrypoint.sh"]
