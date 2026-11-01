import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import psycopg # type: ignore
from psycopg import sql # type: ignore
from dotenv import load_dotenv

load_dotenv()

# Identificadores SQL vêm exclusivamente daqui, nunca da entrada do usuário.
TABLES = {
    "customers": {
        "columns": ("id", "name", "email", "signup_date"),
        "key": "id",
        "ddl": """CREATE TABLE IF NOT EXISTS raw.customers (
            id INTEGER PRIMARY KEY, name TEXT, email TEXT, signup_date DATE
        )""",
    },
    "products": {
        "columns": ("product_id", "name", "category", "cost", "price"),
        "key": "product_id",
        "ddl": """CREATE TABLE IF NOT EXISTS raw.products (
            product_id INTEGER PRIMARY KEY, name TEXT, category TEXT,
            cost NUMERIC(12, 2), price NUMERIC(12, 2)
        )""",
    },
    "orders": {
        "columns": ("order_id", "customer_id", "order_date", "status"),
        "key": "order_id",
        "ddl": """CREATE TABLE IF NOT EXISTS raw.orders (
            order_id BIGINT PRIMARY KEY, customer_id INTEGER,
            order_date DATE, status TEXT
        )""",
    },
    "order_items": {
        "columns": ("order_item_id", "order_id", "product_id", "quantity"),
        "key": "order_item_id",
        "ddl": """CREATE TABLE IF NOT EXISTS raw.order_items (
            order_item_id BIGINT PRIMARY KEY, order_id BIGINT,
            product_id INTEGER, quantity INTEGER
        )""",
    },
    "cancelamentos": {
        "columns": ("order_id", "cancel_reason", "cancel_date"),
        "key": "order_id",
        "ddl": """CREATE TABLE IF NOT EXISTS raw.cancelamentos (
            order_id BIGINT PRIMARY KEY, cancel_reason TEXT, cancel_date DATE
        )""",
    },
}


def get_connection_config() -> dict:
    return {
        "host": os.environ["DBT_HOST"],
        "user": os.environ["DBT_USER"],
        "password": os.environ["DBT_ENV_SECRET_PASSWORD"],
        "dbname": os.environ["DBT_DATABASE"],
        "port": int(os.getenv("DBT_PORT", "5432")),
    }


def batch_dir(run_id: str) -> Path:
    if not run_id.strip():
        raise ValueError("--run-id não pode ser vazio")
    key = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:16]
    return Path(os.environ["OUTPUT_PATH"]) / "batches" / key


def get_validated_csv(table_name: str, run_id: str) -> Path:
    path = batch_dir(run_id)
    manifest_file = path / "manifest.json"
    if not manifest_file.is_file():
        raise FileNotFoundError(f"Lote ainda não finalizado: {manifest_file}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("run_id") != run_id:
        raise ValueError("run_id não corresponde ao manifesto")

    file_path = path / f"{table_name}.csv"
    if not file_path.is_file():
        raise FileNotFoundError(file_path)

    with file_path.open("r", encoding="utf-8-sig", newline="") as fh:
        header = next(csv.reader(fh), None)
    if header != list(TABLES[table_name]["columns"]):
        raise ValueError(f"Cabeçalho inválido em {file_path}: {header}")
    return file_path


def load_table(table_name: str, run_id: str) -> tuple[int, int]:
    """Retorna (linhas_do_lote, linhas_inseridas_ou_atualizadas)."""
    if table_name not in TABLES:
        raise ValueError(f"Tabela desconhecida: {table_name}")

    config = TABLES[table_name]
    csv_path = get_validated_csv(table_name, run_id)
    columns = config["columns"]
    key = config["key"]
    nonkeys = [name for name in columns if name != key]

    target = sql.Identifier("raw", table_name)
    staging = sql.Identifier("_stage_" + table_name)
    col_list = sql.SQL(", ").join(map(sql.Identifier, columns))

    with psycopg.connect(**get_connection_config()) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS raw")
            cur.execute(config["ddl"])
            # A tabela temporária tem os tipos da tabela destino, sem copiar PK/índices.
            cur.execute(
                sql.SQL("CREATE TEMP TABLE {} (LIKE {}) ON COMMIT DROP").format(staging, target)
            )
            copy_stmt = sql.SQL(
                "COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
            ).format(staging, col_list)
            with cur.copy(copy_stmt) as copy:
                with csv_path.open("rb") as fh:
                    while chunk := fh.read(65536):
                        copy.write(chunk)

            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(staging))
            staged = cur.fetchone()[0]

            set_clause = sql.SQL(", ").join(
                sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
                for c in nonkeys
            )
            existing = sql.SQL(", ").join(
                sql.SQL("dest.{}").format(sql.Identifier(c)) for c in nonkeys
            )
            incoming = sql.SQL(", ").join(
                sql.SQL("EXCLUDED.{}").format(sql.Identifier(c)) for c in nonkeys
            )
            # WHERE is distinct evita updates desnecessários em reexecuções.
            upsert = sql.SQL("""
                INSERT INTO {} AS dest ({})
                SELECT {} FROM {} WHERE TRUE
                ON CONFLICT ({}) DO UPDATE SET {}
                WHERE ({}) IS DISTINCT FROM ({})
            """).format(
                target, col_list, col_list, staging,
                sql.Identifier(key), set_clause, existing, incoming,
            )
            cur.execute(upsert)
            changed = cur.rowcount

    print(f"[OK] raw.{table_name}: {staged} linhas no lote; {changed} inseridas/alteradas")
    return staged, changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestão incremental em raw")
    parser.add_argument("table", choices=sorted(TABLES))
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    load_table(args.table, args.run_id)


if __name__ == "__main__":
    main()