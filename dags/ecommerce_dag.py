import os
import sys
import subprocess
from datetime import datetime, timedelta

from airflow.sdk import DAG # type: ignore
from airflow.providers.standard.operators.python import PythonOperator # type: ignore
from airflow.providers.standard.operators.bash import BashOperator # type: ignore

SCRIPT_PATH = os.environ["SCRIPT_PATH"]
DBT_PROJECT_DIR = os.environ["DBT_PROJECT_DIR"]
DBT_PROFILES_DIR = os.environ["DBT_PROFILES_DIR"]
DBT_BIN = "/usr/local/airflow/dbt_venv/bin/dbt"
HISTORY_RUN_ID = "historical-bootstrap-v1"

DATA_TABLES = (
    "customers",
    "products",
    "orders",
    "order_items",
    "cancelamentos",
)

def bootstrap_history(**context):
    """Create and ingest the historical sample idempotently."""

    run_date = context["ds"]

    subprocess.run(
        [
            sys.executable,
            os.path.join(SCRIPT_PATH, "generate_fake_data.py"),
            "--run-id", HISTORY_RUN_ID,
            "--run-date", run_date,
            "--mode", "history",
        ],
        check=True,
    )

    for table in DATA_TABLES:
        subprocess.run(
            [
                sys.executable,
                os.path.join(SCRIPT_PATH, "load_data.py"),
                table,
                "--run-id", HISTORY_RUN_ID,
            ],
            check=True,
        )

def generate_data(**context):
    subprocess.run(
        [
            sys.executable,
            os.path.join(SCRIPT_PATH, "generate_fake_data.py"),
            "--run-id", context["run_id"],
            "--run-date", context["ds"],
        ],
        check=True,
    )


def load_data(table_name: str, **context):
    subprocess.run(
        [
            sys.executable,
            os.path.join(SCRIPT_PATH, "load_data.py"),
            table_name,
            "--run-id", context["run_id"],
        ],
        check=True,
    )


def dbt_command(subcommand: str) -> str:
    return (
        f"{DBT_BIN} {subcommand} "
        f'--project-dir "{DBT_PROJECT_DIR}" '
        f'--profiles-dir "{DBT_PROFILES_DIR}"'
    )


def run_report(**context):
    subprocess.run(
        [
            sys.executable,
            os.path.join(SCRIPT_PATH, "generate_report.py"),
            "--run-id",
            context["run_id"],
        ],
        check=True,
    )


default_args = {
    "owner": "Ayrton",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="ecommerce_analytics_dag",
    default_args=default_args,
    start_date=datetime(2026, 10, 29),
    schedule="@weekly",
    catchup=False,
    tags=["ecommerce", "analytics", "churn"],
    max_active_runs=1,
) as dag:
    t_generate = PythonOperator(task_id="generate_fake_data", python_callable=generate_data)
    loads = [
        PythonOperator(
            task_id=f"load_{table}",
            python_callable=load_data,
            op_kwargs={"table_name": table},
        )
        for table in ("customers", "products", "orders", "order_items", "cancelamentos")
    ]
    t_dbt_run = BashOperator(task_id="dbt_run", bash_command=dbt_command("run"))
    t_dbt_test = BashOperator(task_id="dbt_test", bash_command=dbt_command("test"))
    t_report = PythonOperator(task_id="generate_report", python_callable=run_report)
    t_bootstrap = PythonOperator(task_id="bootstrap_history", python_callable=bootstrap_history)


    previous = t_bootstrap >> t_generate
    for task in loads:
        previous >> task
        previous = task
    previous >> t_dbt_run >> t_dbt_test >> t_report
