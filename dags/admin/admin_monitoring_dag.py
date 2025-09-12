from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# Default arguments for Admin DAGs
default_args = {
    'owner': 'admin',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Python functions for admin tasks
def check_edge_workers_status():
    """Check status of all edge workers"""
    import json
    
    print("=== Edge Workers Status Check ===")
    
    # Simulate checking edge worker status
    edge_workers = [
        {
            "name": "team_a_worker",
            "queue": "team_a_queue",
            "status": "active",
            "tasks_processed": 45,
            "cpu_usage": 15.4,
            "memory_usage": 234.7,
            "last_heartbeat": datetime.now().isoformat()
        },
        {
            "name": "team_b_worker", 
            "queue": "team_b_queue",
            "status": "active",
            "tasks_processed": 38,
            "cpu_usage": 22.1,
            "memory_usage": 189.3,
            "last_heartbeat": datetime.now().isoformat()
        }
    ]
    
    print("Edge Workers Status:")
    for worker in edge_workers:
        status_emoji = "🟢" if worker["status"] == "active" else "🔴"
        print(f"  {status_emoji} {worker['name']} ({worker['queue']})")
        print(f"    Tasks: {worker['tasks_processed']}, CPU: {worker['cpu_usage']}%, Memory: {worker['memory_usage']}MB")
        
    return {"edge_workers": edge_workers}

def analyze_team_dag_performance():
    """Analyze performance across teams"""
    import json
    
    print("=== Team DAG Performance Analysis ===")
    
    # Simulate performance data
    performance_data = {
        "team_a": {
            "total_dags": 2,
            "success_rate": 98.5,
            "avg_execution_time_minutes": 4.2,
            "total_task_runs_today": 24,
            "failed_tasks_today": 0
        },
        "team_b": {
            "total_dags": 2,
            "success_rate": 97.8,
            "avg_execution_time_minutes": 6.1,
            "total_task_runs_today": 18,
            "failed_tasks_today": 1
        }
    }
    
    print("Team Performance Summary:")
    for team, data in performance_data.items():
        print(f"\n{team.upper()}:")
        print(f"  Success Rate: {data['success_rate']}%")
        print(f"  Avg Execution Time: {data['avg_execution_time_minutes']} minutes")
        print(f"  Tasks Today: {data['total_task_runs_today']} (Failed: {data['failed_tasks_today']})")
    
    # Generate recommendations
    recommendations = []
    for team, data in performance_data.items():
        if data['success_rate'] < 98:
            recommendations.append(f"Consider investigating {team} DAG failures")
        if data['avg_execution_time_minutes'] > 5:
            recommendations.append(f"Optimize {team} DAG performance")
    
    if recommendations:
        print("\nRecommendations:")
        for rec in recommendations:
            print(f"  • {rec}")
    else:
        print("\nNo performance issues detected - all teams performing well!")
    
    return {"performance": performance_data, "recommendations": recommendations}

def generate_system_report(**context):
    """Generate overall system report"""
    print("=== System Report ===")
    print(f"Report Date: {context['ds']}")
    print(f"DAG Run ID: {context['run_id']}")
    
    # System health summary
    system_health = {
        "edge_executor_status": "healthy",
        "database_status": "healthy", 
        "total_edge_workers": 2,
        "active_edge_workers": 2,
        "total_teams": 2,
        "monitoring_status": "active"
    }
    
    print("\nSystem Health:")
    for component, status in system_health.items():
        status_emoji = "✅" if status in ["healthy", "active", 2] else "⚠️"
        print(f"  {status_emoji} {component.replace('_', ' ').title()}: {status}")
    
    print("\nMulti-Team EdgeExecutor Setup:")
    print("  • Team A: Data analytics with pandas/numpy")
    print("  • Team B: API services with FastAPI/boto3") 
    print("  • Isolation: Separate Docker containers and queues")
    print("  • RBAC: Role-based access control enabled")
    
    return {"system_health": system_health}

# Admin Monitoring DAG
dag = DAG(
    'admin_monitoring_dag',
    default_args=default_args,
    description='Admin DAG for monitoring EdgeExecutor and team DAGs',
    schedule_interval=timedelta(minutes=30),
    catchup=False,
    tags=['admin', 'monitoring', 'edge_executor'],
)

# Task 1: Check system health
health_check_task = BashOperator(
    task_id='system_health_check',
    bash_command='''
    echo "=== System Health Check ==="
    echo "Timestamp: $(date)"
    echo "Hostname: $(hostname)"
    echo "Uptime: $(uptime)"
    echo "Disk Usage:"
    df -h | head -5
    echo "Memory Usage:"
    free -h
    ''',
    dag=dag,
)

# Task 2: Check edge workers
edge_workers_task = PythonOperator(
    task_id='check_edge_workers',
    python_callable=check_edge_workers_status,
    dag=dag,
)

# Task 3: Analyze team performance
performance_task = PythonOperator(
    task_id='analyze_team_performance',
    python_callable=analyze_team_dag_performance,
    dag=dag,
)

# Task 4: Generate system report
report_task = PythonOperator(
    task_id='generate_system_report',
    python_callable=generate_system_report,
    dag=dag,
)

# Task 5: Check DAG files
dag_files_check_task = BashOperator(
    task_id='check_dag_files',
    bash_command='''
    echo "=== DAG Files Check ==="
    echo "Team A DAGs:"
    find dags/team_a -name "*.py" -type f | wc -l
    echo "Team B DAGs:"  
    find dags/team_b -name "*.py" -type f | wc -l
    echo "Admin DAGs:"
    find dags/admin -name "*.py" -type f | wc -l
    echo "Total DAG files:"
    find dags -name "*.py" -type f | wc -l
    ''',
    dag=dag,
)

# Set task dependencies
health_check_task >> [edge_workers_task, performance_task] >> dag_files_check_task >> report_task
