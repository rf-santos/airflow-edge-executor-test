FROM apache/airflow:2.10.5-python3.12

ENV PIP_NO_CACHE_DIR=1 \
    AIRFLOW__CORE__LOAD_EXAMPLES=False

USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Testbed RBAC setup script
COPY scripts/ /opt/airflow/scripts/
RUN chmod +x /opt/airflow/scripts/*.py
RUN chmod +x /opt/airflow/scripts/*.sh
## NOTE: Do NOT run the RBAC bootstrap at build time because it requires a configured
## metadata database (Airflow app context). We will execute it after `airflow db init`
## using a runtime command (e.g., in airflow-init or manually via docker compose exec).

USER airflow

# Upgrade pydantic (base image pins 2.10.x) then install edge provider (requires >=2.11.0)
RUN pip install --no-cache-dir --upgrade "pydantic>=2.11.0,<3" \
    && pip install --no-cache-dir apache-airflow-providers-edge3==1.1.3

# (Optional) place for additional central-only dependencies