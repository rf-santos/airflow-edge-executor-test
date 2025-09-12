from ast import mod
from asyncio import Task
from datetime import datetime, timedelta
import queue
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor

# Default arguments for Team B DAGs
default_args = {
    "owner": "team_b",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


# Python functions for Team B tasks
def team_b_api_request():
    """Simulate an API request using requests library"""
    try:
        import requests

        response = requests.get("https://jsonplaceholder.typicode.com/posts/1")
        if response.status_code == 200:
            data = response.json()
            print("API Response:", data)
            return data
        else:
            print(f"Failed to fetch data, status code: {response.status_code}")
            return {"error": f"Status code {response.status_code}"}

    except ImportError as e:
        print(f"Required package not available: {e}")
        return {"error": str(e)}


# Create a DAG dependency on team_a_python_dag
# Team B Python DAG
dag = DAG(
    "team_b_python_dag",
    default_args=default_args,
    description="Team B Python DAG with PythonOperator and team-specific libraries",
    schedule=timedelta(minutes=5),
    catchup=False,
    tags=["team_b", "python", "api_services", "cloud"],
)

# Sensor to wait for Team A's DAG to complete
wait_for_team_a = ExternalTaskSensor(
    task_id="wait_for_team_a_dag",
    external_dag_id="team_a_python_dag",
    external_task_id="team_a_data_processing",
    allowed_states=["success"],
    failed_states=["failed", "skipped"],
    mode="reschedule",
    deferrable=True,
    queue="team_b_queue",
    pool="team_b_pool",
    dag=dag,
)

# Task 1: API request simulation
api_request = PythonOperator(
    task_id="team_b_api_request",
    python_callable=team_b_api_request,
    queue="team_b_queue",
    pool="team_b_pool",
    dag=dag,
)

# Define task dependencies
wait_for_team_a >> api_request
# api_request
