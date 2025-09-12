#! /bin/bash

echo '[airflow-init] Starting metadata migration'
airflow db migrate
echo '[airflow-init] Ensuring default admin user'
airflow users create --username admin --firstname Admin --lastname User --role Admin --email admin@example.com --password admin || true
echo '[airflow-init] Syncing permissions'
airflow sync-perm || true
echo '[airflow-init] Creating team pools'
airflow pools set team_a_pool 10 "Pool for Team A" || true
airflow pools set team_b_pool 10 "Pool for Team B" || true
echo '[airflow-init] Completed.'