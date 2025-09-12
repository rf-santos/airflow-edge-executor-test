from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Default arguments for Team A DAGs
default_args = {
    "owner": "team_a",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "pool": "team_a_pool",  # Default pool for all tasks in this DAG
    "queue": "team_a_queue",  # Default queue for all tasks in this DAG
}


# Python functions for Team A tasks
def team_a_data_processing():
    """Team A specific data processing function using pandas"""
    try:
        import pandas as pd
        import numpy as np

        # Create sample data
        data = {
            "team": ["Team A"] * 5,
            "metric": [
                "cpu_usage",
                "memory_usage",
                "disk_io",
                "network_io",
                "response_time",
            ],
            "value": np.random.rand(5) * 100,
        }

        df = pd.DataFrame(data)
        print("Team A Data Processing:")
        print(df.to_string(index=False))

        # Basic statistics
        print(f"\nMean value: {df['value'].mean():.2f}")
        print(f"Max value: {df['value'].max():.2f}")

        return df.to_dict()

    except ImportError as e:
        print(f"Required package not available: {e}")
        return {"error": str(e)}


# Team A Python DAG
dag = DAG(
    "team_a_python_dag",
    default_args=default_args,
    description="Team A Python DAG with PythonOperator and team-specific libraries",
    schedule=timedelta(minutes=1),
    catchup=False,
    tags=["team_a", "python", "data_processing"],
)

# Task 1: Data processing with pandas
data_processing_task = PythonOperator(
    task_id="team_a_data_processing",
    python_callable=team_a_data_processing,
    # queue="team_a_queue",
    # pool="team_a_pool",
    dag=dag,
)

# Single task DAG; no explicit dependencies needed
