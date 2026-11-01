import argparse
import os
import psycopg # type: ignore
from psycopg import sql # type: ignore
from load_data import get_connection_config


def run_migration(confirm: bool) -> None:
    with psycopg.connect(**get_connection_config()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('raw.orders'), to_regclass('raw.order_items')")
            orders_exists, items_exists = cur.fetchone()
            if orders_exists is None and items_exists is None:
                print("[OK] Banco novo: tabelas serão criadas pelo load_data.py.")
                return
            if orders_exists is None or items_exists is None:
                raise RuntimeError("Esquema raw parcialmente criado. Revise manualmente.")

            cur.execute("""
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'raw'
                  AND (table_name, column_name) IN (
                    ('orders', 'order_id'),
                    ('order_items', 'order_id'),
                    ('order_items', 'order_item_id'),
                    ('cancelamentos', 'order_id')
                  )
            """)
            actual = {(t, c): dtype for t, c, dtype in cur.fetchall()}
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'raw.order_items'::regclass AND contype = 'p'
                )
            """)
            has_items_pk = cur.fetchone()[0]
            needed = (
                not has_items_pk
                or
                actual.get(("orders", "order_id")) != "bigint"
                or actual.get(("order_items", "order_id")) != "bigint"
                or actual.get(("order_items", "order_item_id")) != "bigint"
                or (actual.get(("cancelamentos", "order_id")) not in ("bigint", None))
            )
            if not needed:
                print("[OK] Estrutura já suporta incrementalidade; nenhuma migração necessária.")
                return
            if not confirm:
                raise RuntimeError(
                    "Migração necessária. Ela remove APENAS o schema analytics, "
                    "que deverá ser recriado pelo dbt. Execute com --confirm-drop-analytics "
                    "se analytics contiver somente objetos reconstruíveis pelo dbt."
                )


            analytics_schema = os.environ.get("DBT_SCHEMA", "analytics")
            if analytics_schema == "raw":
                raise ValueError("DBT_SCHEMA não pode ser raw para esta migração")
            cur.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(analytics_schema)
                )
            )
            cur.execute("ALTER TABLE raw.orders ALTER COLUMN order_id TYPE BIGINT")
            cur.execute("ALTER TABLE raw.order_items ALTER COLUMN order_id TYPE BIGINT")
            if actual.get(("cancelamentos", "order_id")) is not None:
                cur.execute("ALTER TABLE raw.cancelamentos ALTER COLUMN order_id TYPE BIGINT")
            cur.execute("ALTER TABLE raw.order_items ADD COLUMN IF NOT EXISTS order_item_id BIGINT")
            cur.execute("ALTER TABLE raw.order_items ALTER COLUMN order_item_id TYPE BIGINT")

            cur.execute("""
                WITH missing AS (
                    SELECT ctid, -ROW_NUMBER() OVER (ORDER BY ctid) AS item_id
                    FROM raw.order_items
                    WHERE order_item_id IS NULL
                )
                UPDATE raw.order_items t
                SET order_item_id = missing.item_id
                FROM missing
                WHERE t.ctid = missing.ctid
            """)
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'raw.order_items'::regclass AND contype = 'p'
                    ) THEN
                        ALTER TABLE raw.order_items
                        ADD CONSTRAINT order_items_pkey PRIMARY KEY (order_item_id);
                    END IF;
                END $$;
            """)
            print("[OK] BIGINT e order_item_id migrados; raw preservado.")
            print("[INFO] Schema de modelos dbt removido; execute dbt run após as cargas.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-drop-analytics", action="store_true")
    args = parser.parse_args()
    run_migration(args.confirm_drop_analytics)
