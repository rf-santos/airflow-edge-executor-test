#!/usr/bin/env bash
set -euo pipefail

# Cloud Run passes PORT; we'll listen on it with a simple health server
: "${PORT:=8080}"

# Required environment variables for secure connection to Composer
# AIRFLOW__EDGE__API_URL - Composer Public (or Private with VPC) Edge RPC URL, e.g., https://<WEBSERVER_URL>/edge_worker/v1/rpcapi
# AIRFLOW__EDGE__EDGE_WORKER_API_SECRET_KEY - must match Composer's airflow.cfg [edge] secret
# EDGE_EXECUTOR_QUEUES - comma separated queues, e.g., team_a_queue
# EDGE_EXECUTOR_HOSTNAME - unique worker hostname to display in logs
# EDGE_EXECUTOR_CONCURRENCY - default 4
# EDGE_EXECUTOR_POLL_INTERVAL - default 5
# EDGE_EXECUTOR_HEARTBEAT_INTERVAL - default 30

EDGE_EXECUTOR_CONCURRENCY=${EDGE_EXECUTOR_CONCURRENCY:-4}
EDGE_EXECUTOR_POLL_INTERVAL=${EDGE_EXECUTOR_POLL_INTERVAL:-5}
EDGE_EXECUTOR_HEARTBEAT_INTERVAL=${EDGE_EXECUTOR_HEARTBEAT_INTERVAL:-30}

if [[ -z "${AIRFLOW__EDGE__API_URL:-}" ]]; then
  echo "AIRFLOW__EDGE__API_URL is required" >&2
  exit 1
fi
if [[ -z "${AIRFLOW__EDGE__EDGE_WORKER_API_SECRET_KEY:-}" ]]; then
  echo "AIRFLOW__EDGE__EDGE_WORKER_API_SECRET_KEY is required" >&2
  exit 1
fi
if [[ -z "${EDGE_EXECUTOR_QUEUES:-}" ]]; then
  echo "EDGE_EXECUTOR_QUEUES is required" >&2
  exit 1
fi
if [[ -z "${EDGE_EXECUTOR_HOSTNAME:-}" ]]; then
  echo "EDGE_EXECUTOR_HOSTNAME is required" >&2
  exit 1
fi

# Start health server in background
python /opt/edge/healthz.py &
HEALTH_PID=$!

# Export core Edge configs for Airflow process
export AIRFLOW__EDGE__API_ENABLED=True
export AIRFLOW__EDGE__JOB_POLL_INTERVAL=${EDGE_EXECUTOR_POLL_INTERVAL}
export AIRFLOW__EDGE__HEARTBEAT_INTERVAL=${EDGE_EXECUTOR_HEARTBEAT_INTERVAL}

# Print config for debugging
echo "Starting Edge Worker with the following configuration:"
echo "-----------------------------------------------"
echo "PORT: $PORT"
echo "AIRFLOW__EDGE__EDGE_WORKER_API_SECRET_KEY: ${#AIRFLOW__EDGE__EDGE_WORKER_API_SECRET_KEY} characters"
echo "AIRFLOW__EDGE__API_ENABLED: $AIRFLOW__EDGE__API_ENABLED"
echo "AIRFLOW__EDGE__API_URL: $AIRFLOW__EDGE__API_URL"
echo "EDGE_EXECUTOR_QUEUES: $EDGE_EXECUTOR_QUEUES"
echo "EDGE_EXECUTOR_HOSTNAME: $EDGE_EXECUTOR_HOSTNAME"
echo "EDGE_EXECUTOR_CONCURRENCY: $EDGE_EXECUTOR_CONCURRENCY"
echo "EDGE_EXECUTOR_POLL_INTERVAL: $EDGE_EXECUTOR_POLL_INTERVAL"
echo "EDGE_EXECUTOR_HEARTBEAT_INTERVAL: $EDGE_EXECUTOR_HEARTBEAT_INTERVAL"

### Ensure executor module import registers CLI group
python - <<'PY'
import sys
try:
    import airflow, airflow.providers.edge3.executors.edge_executor  # noqa: F401
    import airflow.providers.edge3.cli.edge_command  # noqa: F401
    print(f"Edge executor & CLI imported (Airflow {airflow.__version__})")
except Exception as e:
    print(f"FAILED_EDGE_IMPORT: {e}", file=sys.stderr)
    sys.exit(2)
PY

exec airflow edge worker \
  --queues "${EDGE_EXECUTOR_QUEUES}" \
  --concurrency "${EDGE_EXECUTOR_CONCURRENCY}" \
  --edge-hostname "${EDGE_EXECUTOR_HOSTNAME}"