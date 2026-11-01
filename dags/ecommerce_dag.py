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


def generate_data():
    subprocess.run(
        [sys.executable, os.path.join(SCRIPT_PATH, "generate_fake_data.py")],
        check=True,
    )


def load_command(table_name: str) -> str:
    # Nomes fixos definidos na DAG; não recebem entrada externa.
    script = os.path.join(SCRIPT_PATH, "load_data.py")
    return f'python "{script}" {table_name}'


def dbt_command(subcommand: str) -> str:
    return (
        f"{DBT_BIN} {subcommand} "
        f'--project-dir "{DBT_PROJECT_DIR}" '
        f'--profiles-dir "{DBT_PROFILES_DIR}"'
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
    t_generate = PythonOperator(
        task_id="generate_fake_data",
        python_callable=generate_data,
    )

    t_load_customers = BashOperator(
        task_id="load_customers",
        bash_command=load_command("customers"),
    )
    t_load_products = BashOperator(
        task_id="load_products",
        bash_command=load_command("products"),
    )
    t_load_orders = BashOperator(
        task_id="load_orders",
        bash_command=load_command("orders"),
    )
    t_load_order_items = BashOperator(
        task_id="load_order_items",
        bash_command=load_command("order_items"),
    )
    t_load_cancelamentos = BashOperator(
        task_id="load_cancelamentos",
        bash_command=load_command("cancelamentos"),
    )

    t_dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=dbt_command("run"),
    )
    t_dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=dbt_command("test"),
    )
    t_generate_report = BashOperator(
        task_id="generate_report",
        bash_command=f'python "{os.path.join(SCRIPT_PATH, "generate_report.py")}"',
    )

    (
        t_generate
        >> t_load_customers
        >> t_load_products
        >> t_load_orders
        >> t_load_order_items
        >> t_load_cancelamentos
        >> t_dbt_run
        >> t_dbt_test
        >> t_generate_report
    )
