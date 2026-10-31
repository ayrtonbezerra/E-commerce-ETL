import os
import sys
import subprocess

from datetime import datetime, timedelta
from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.operators.bash import BashOperator

SCRIPT_PATH = os.environ["SCRIPT_PATH"]
DBT_PROJECT_DIR = os.environ["DBT_PROJECT_DIR"]
DBT_PROFILES_DIR = os.environ["DBT_PROFILES_DIR"]

DBT_BIN = "/usr/local/airflow/dbt_venv/bin/dbt"


def generate_data():
    subprocess.run(
        [sys.executable, os.path.join(SCRIPT_PATH, "generate_fake_data.py")],
        check=True
    )


default_args = {
    "owner": "Ayrton",
    "retries": 1,
    "retry_delay": timedelta(minutes=5)
}


with DAG(
    dag_id="ecommerce_analytics_dag",
    default_args=default_args,
    start_date=datetime(2026, 10, 29),
    schedule="@weekly",
    catchup=False,
    tags=["ecommerce", "analytics", "churn"],
    max_active_runs = 1
) as dag:

    t1_generate_fake_data = PythonOperator(
        task_id="generate_fake_data",
        python_callable=generate_data
    )

    t2_dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=(
            f'{DBT_BIN} seed '
            f'--project-dir "{DBT_PROJECT_DIR}" '
            f'--profiles-dir "{DBT_PROFILES_DIR}"'
        )
    )

    t3_dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f'{DBT_BIN} run '
            f'--project-dir "{DBT_PROJECT_DIR}" '
            f'--profiles-dir "{DBT_PROFILES_DIR}"'
        )
    )

    t4_dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f'{DBT_BIN} test '
            f'--project-dir "{DBT_PROJECT_DIR}" '
            f'--profiles-dir "{DBT_PROFILES_DIR}"'
        )
    )

    t5_generate_report = BashOperator(
        task_id="generate_report",
        bash_command=(
            f'python "{os.path.join(SCRIPT_PATH, "generate_report.py")}"'
        )
    )

    (
        t1_generate_fake_data
        >> t2_dbt_seed
        >> t3_dbt_run
        >> t4_dbt_test
        >> t5_generate_report
    )