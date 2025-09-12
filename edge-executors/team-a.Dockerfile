FROM apache/airflow:2.10.5-python3.12

# Pin provider version compatible with Airflow 2.10.x (newer 1.2.x requires >=2.11 for dynamic provider info)
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    AIRFLOW__CORE__LOAD_EXAMPLES=False \
    AIRFLOW__CORE__EXECUTOR=airflow.providers.edge3.executors.edge_executor.EdgeExecutor \
    AIRFLOW_VERSION=2.10.5 \
    PYTHON_MAJOR_MINOR=3.12 \
    EDGE_PROVIDER_VERSION=1.1.3

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY edge-executors/entrypoint.sh /opt/edge/entrypoint.sh
COPY edge-executors/healthz.py /opt/edge/healthz.py
RUN chmod +x /opt/edge/entrypoint.sh

USER airflow

# Install EdgeExecutor provider (pin 1.1.3) and team-specific requirements (upgrade pydantic first)
RUN pip install --no-cache-dir "pydantic>=2.11.0,<3" \
    && pip install --no-cache-dir "apache-airflow-providers-edge3==${EDGE_PROVIDER_VERSION}"
COPY edge-executors/requirements.team-a.txt /opt/edge/requirements.team-a.txt
RUN pip install --no-cache-dir -r /opt/edge/requirements.team-a.txt

ENTRYPOINT ["/opt/edge/entrypoint.sh"]
