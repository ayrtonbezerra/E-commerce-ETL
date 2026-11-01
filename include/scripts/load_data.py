import argparse
import csv
import os
from pathlib import Path

import psycopg # type: ignore
from dotenv import load_dotenv

load_dotenv()

# Lista fechada de tabelas: o argumento da CLI nunca vira SQL arbitrário.
TABLES = {
    "customers": {
        "columns": ("id", "name", "email", "signup_date"),
        "ddl": """
            CREATE TABLE IF NOT EXISTS raw.customers (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT,
                signup_date DATE
            )
        """,
    },
    "products": {
        "columns": ("product_id", "name", "category", "cost", "price"),
        "ddl": """
            CREATE TABLE IF NOT EXISTS raw.products (
                product_id INTEGER PRIMARY KEY,
                name TEXT,
                category TEXT,
                cost NUMERIC(12, 2),
                price NUMERIC(12, 2)
            )
        """,
    },
    "orders": {
        "columns": ("order_id", "customer_id", "order_date", "status"),
        "ddl": """
            CREATE TABLE IF NOT EXISTS raw.orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                order_date DATE,
                status TEXT
            )
        """,
    },
    "order_items": {
        "columns": ("order_id", "product_id", "quantity"),
        "ddl": """
            CREATE TABLE IF NOT EXISTS raw.order_items (
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER
            )
        """,
    },
    "cancelamentos": {
        "columns": ("order_id", "cancel_reason", "cancel_date"),
        "ddl": """
            CREATE TABLE IF NOT EXISTS raw.cancelamentos (
                order_id INTEGER PRIMARY KEY,
                cancel_reason TEXT,
                cancel_date DATE
            )
        """,
    },
}


def get_connection_config() -> dict:
    """Reutiliza as credenciais já existentes no .env do projeto."""
    return {
        "host": os.environ["DBT_HOST"],
        "user": os.environ["DBT_USER"],
        "password": os.environ["DBT_ENV_SECRET_PASSWORD"],
        "dbname": os.environ["DBT_DATABASE"],
        "port": int(os.getenv("DBT_PORT", "5432")),
    }


def load_table(table_name: str) -> int:
    """Substitui o conteúdo de raw.<tabela> pelo CSV, em transação única."""
    if table_name not in TABLES:
        raise ValueError(f"Tabela desconhecida: {table_name}")

    config = TABLES[table_name]
    csv_path = Path(os.environ["OUTPUT_PATH"]) / f"{table_name}.csv"
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV não encontrado: {csv_path}")

    # Evita carregar silenciosamente arquivos com cabeçalho incorreto.
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        header = next(csv.reader(file), None)
    expected = list(config["columns"])
    if header != expected:
        raise ValueError(
            f"Cabeçalho inválido em {csv_path}: {header}. Esperado: {expected}"
        )

    columns_sql = ", ".join(config["columns"])
    copy_sql = (
        f"COPY raw.{table_name} ({columns_sql}) "
        "FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
    )

    # A conexão confirma (commit) somente se a carga inteira funcionar.
    # Se COPY falhar, CREATE/TRUNCATE/COPY são revertidos (rollback).
    with psycopg.connect(**get_connection_config()) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS raw")
            cur.execute(config["ddl"])
            cur.execute(f"TRUNCATE TABLE raw.{table_name}")

            with cur.copy(copy_sql) as copy:
                with csv_path.open("rb") as file:
                    while chunk := file.read(64 * 1024):
                        copy.write(chunk)

            cur.execute(f"SELECT COUNT(*) FROM raw.{table_name}")
            row_count = cur.fetchone()[0]

    print(f"[OK] raw.{table_name}: {row_count} registros carregados de {csv_path}")
    return row_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Carrega um CSV na camada raw")
    parser.add_argument("table", choices=sorted(TABLES))
    args = parser.parse_args()
    load_table(args.table)


if __name__ == "__main__":
    main()
