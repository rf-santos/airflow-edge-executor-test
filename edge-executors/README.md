# Airflow EdgeExecutor on Cloud Run

This folder provides a reusable Docker image and entrypoint for running Airflow Edge workers on Cloud Run. You can deploy one service per team (e.g., Team A and Team B) and isolate access via queues, pools, and IAM.

## Image overview
- Base: `apache/airflow:2.10.5-python3.12`
- Installs minimal extra packages from `requirements.txt`
- `entrypoint.sh` starts a tiny health server on `$PORT` and then runs `airflow edge worker`
- Configuration is entirely via environment variables

Key env vars:
- `AIRFLOW__EDGE__API_URL` – Composer Edge RPC endpoint, like `https://<composer-webserver>/edge_worker/v1/rpcapi`
- `AIRFLOW__EDGE__EDGE_WORKER_API_SECRET_KEY` – must match Composer `[edge] edge_worker_api_secret_key`
- `EDGE_EXECUTOR_QUEUES` – comma-separated queues the worker serves (e.g., `team_a_queue`)
- `EDGE_EXECUTOR_HOSTNAME` – unique worker hostname label
- Optional: `EDGE_EXECUTOR_CONCURRENCY`, `EDGE_EXECUTOR_POLL_INTERVAL`, `EDGE_EXECUTOR_HEARTBEAT_INTERVAL`

## Build & Push
Use Artifact Registry:
1. Create repo (once):
  ```sh
  gcloud artifacts repositories create airflow-edge \
    --repository-format=docker \
    --location=europe-west1 \
    --description="Airflow EdgeExecutors"
  ```
2. Build & push (shared minimal image):
  ```sh
  PROJECT_ID=$(gcloud config get-value project)
  REGION=europe-west1
  IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/airflow-edge/edge-executor:latest
  gcloud auth configure-docker $REGION-docker.pkg.dev
  docker build -t $IMAGE -f edge-executors/Dockerfile .
  docker push $IMAGE
  ```

Per-team overlays (adds team-specific Python deps):

- Team A (pandas/numpy):
  ```sh
  IMAGE_A=$REGION-docker.pkg.dev/$PROJECT_ID/airflow-edge/edge-executor-team-a:latest
  docker build -t $IMAGE_A -f edge-executors/team-a.Dockerfile .
  docker push $IMAGE_A
  ```

- Team B (requests only):
  ```sh
  IMAGE_B=$REGION-docker.pkg.dev/$PROJECT_ID/airflow-edge/edge-executor-team-b:latest
  docker build -t $IMAGE_B -f edge-executors/team-b.Dockerfile .
  docker push $IMAGE_B
  ```

> Note: If you rely on deferrable operators (sensors) in Composer, ensure the Composer environment has the Triggerer process enabled; locally this repository includes an `airflow-triggerer` service in `docker-compose.yaml`.

## Create shared secret for secure connection
```sh
PROJECT_ID=$(gcloud config get-value project)
REGION=europe-west1
gcloud secrets create composer-edge-secret --replication-policy=user-managed --project=$PROJECT_ID --locations=$REGION
EDGE_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
printf "%s" "$EDGE_SECRET" | gcloud secrets versions add composer-edge-secret --data-file=-
```

## Deploy Cloud Run (per team)
Important: Because the edge worker is a background process, set `min-instances >= 1` and disable CPU throttling so it keeps polling Composer even without incoming HTTP traffic.
Example for Team A:
```sh
PROJECT_ID=$(gcloud config get-value project)
REGION=europe-west1
IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/airflow-edge/edge-executor:latest
SERVICE=team-a-edge-executor
COMPOSER_EDGE_URL="https://<COMPOSER-WEBSERVER-URL>/edge_worker/v1/rpcapi"
SECRET_REF="projects/$PROJECT_ID/secrets/composer-edge-secret/versions/latest"
VPC_CONNECTOR=edge-connector
VPC_NAME=<YOUR_VPC_NAME>

# Create service account (once)
TEAM_SA=team-a-edge-sa
gcloud iam service-accounts create $TEAM_SA --display-name "Team A EdgeExecutor"

# Allow logging/metrics
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member serviceAccount:$TEAM_SA@$PROJECT_ID.iam.gserviceaccount.com \
  --role roles/logging.logWriter

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member serviceAccount:$TEAM_SA@$PROJECT_ID.iam.gserviceaccount.com \
  --role roles/monitoring.metricWriter

# Allow access to Secret Manager value containing edge secret
gcloud secrets add-iam-policy-binding composer-edge-secret \
  --member serviceAccount:$TEAM_SA@$PROJECT_ID.iam.gserviceaccount.com \
  --role roles/secretmanager.secretAccessor

# Use a Serverless VPC Connector for Private IP Composer webserver
gcloud compute networks vpc-access connectors create $VPC_CONNECTOR \
  --region $REGION \
  --network $VPC_NAME \
  --range 10.8.0.0/28

# Deploy service
gcloud run deploy $SERVICE \
  --image $IMAGE \
  --region $REGION \
  --service-account $TEAM_SA@$PROJECT_ID.iam.gserviceaccount.com \
  --min-instances 1 \
  --max-instances 3 \
  --no-cpu-throttling \
  --cpu 1 \
  --memory 512Mi \
  --port 8080 \
  --ingress internal-and-cloud-load-balancing \
  --no-allow-unauthenticated \
  --vpc-connector edge-connector \
  --vpc-egress private-ranges-only \
  --set-env-vars "AIRFLOW__EDGE__API_URL=$COMPOSER_EDGE_URL,EDGE_EXECUTOR_QUEUES=team_a_queue,EDGE_EXECUTOR_HOSTNAME=team-a-edge-worker" \
  --set-secrets "AIRFLOW__EDGE__EDGE_WORKER_API_SECRET_KEY=$SECRET_REF"
```
Repeat for Team B with its own service, service account, and `EDGE_EXECUTOR_QUEUES=team_b_queue`. If using overlays, deploy Team A with `$IMAGE_A` and Team B with `$IMAGE_B` respectively.

## Composer configuration
In Composer (Airflow 2.10):
- `airflow.cfg` under `[edge]`:
  ```ini
  [edge]
  api_enabled = True
  api_url = https://<composer-webserver-url>/edge_worker/v1/rpcapi
  job_poll_interval = 5
  heartbeat_interval = 30
  edge_worker_api_secret_key = <same-secret-as-Secret-Manager>
  ```
- Define `Pools` and `Queues` (via UI or DAG default args) for `team_a_pool`, `team_b_pool` and queues `team_a_queue`, `team_b_queue`.
- Ensure DAG tasks set `queue` and optionally `pool` to match the team.

## Monitoring & Logging
- Cloud Run logs appear in Cloud Logging; filter by `resource.type=cloud_run_revision` and `resource.labels.service_name`
- Add alerts on error rate and concurrency throttling
- Set `max-instances` and use CPU throttling for cost control
- Use `--min-instances 0` for scale-to-zero (may increase first-run latency)

## Security & Isolation
- Separate Cloud Run services and service accounts per team
- Secret Manager for the Edge secret
- Use VPC connector + Serverless NEG if Composer’s webserver is private; otherwise restrict ingress with IAP or IP allowlist
- IAM on Composer environment to restrict DAG visibility and pools by team where possible

