import argparse
import hashlib
import json
import os
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from faker import Faker


load_dotenv()

CATEGORIES = ["Eletrônicos", "Roupas", "Livros", "Esportes", "Beleza"]
CSV_NAMES = ("customers", "products", "orders", "order_items", "cancelamentos")
ORDER_ID_STRIDE = 100_000


def get_settings() -> tuple[Path, int, int, int]:
    output_path = Path(os.environ["OUTPUT_PATH"])
    n_customers = int(os.environ["N_CUSTOMERS"])
    n_products = int(os.environ["N_PRODUCTS"])
    n_orders = int(os.environ["N_ORDERS"])

    if n_customers < 1 or n_products < 1 or not 1 <= n_orders <= ORDER_ID_STRIDE:
        raise ValueError(
            f"Exigido: N_CUSTOMERS >= 1, N_PRODUCTS >= 1, "
            f"1 <= N_ORDERS <= {ORDER_ID_STRIDE}."
        )
    return output_path, n_customers, n_products, n_orders


def generate_batch(run_id: str, run_date: date) -> Path:
    if not run_id.strip():
        raise ValueError("run_id não pode ser vazio")

    output_path, n_customers, n_products, n_orders = get_settings()
    batch_hash = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    batch_path = output_path / "batches" / batch_hash[:16]
    manifest_path = batch_path / "manifest.json"
    batch_path.mkdir(parents=True, exist_ok=True)

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["run_id"] != run_id or manifest["run_date"] != run_date.isoformat():
            raise ValueError("Manifesto incompatível com run_id / run_date")
        for name in CSV_NAMES:
            if not (batch_path / f"{name}.csv").is_file():
                raise FileNotFoundError(f"CSV faltando no lote finalizado: {name}")
        print(f"[REPLAY] Reutilizando lote já gerado: {batch_path}")
    else:

        base_fake = Faker("pt_BR")
        base_fake.seed_instance(42)
        customers_rng = random.Random(42)
        products_rng = random.Random(43)
        products_fake = Faker("pt_BR")
        products_fake.seed_instance(43)
        base_signup_date = date(2024, 1, 1)

        customers = [
            {
                "id": customer_id,
                "name": base_fake.name(),
                "email": base_fake.email(),
                "signup_date": (base_signup_date + timedelta(days=customers_rng.randint(0, 365))).isoformat(),
            }
            for customer_id in range(1, n_customers + 1)
        ]
        pd.DataFrame(customers).to_csv(batch_path / "customers.csv", index=False)

        products = []
        for product_id in range(1, n_products + 1):
            cost = round(products_rng.uniform(1, 100), 2)
            products.append(
                {
                    "product_id": product_id,
                    "name": f"{products_fake.word().capitalize()} {products_fake.word().capitalize()}",
                    "category": products_rng.choice(CATEGORIES),
                    "cost": cost,
                    "price": round(cost * products_rng.uniform(1.2, 2.5), 2),
                }
            )
        pd.DataFrame(products).to_csv(batch_path / "products.csv", index=False)


        batch_number = int(batch_hash[:10], 16) + 1
        order_start = batch_number * ORDER_ID_STRIDE
        batch_rng = random.Random(int(batch_hash, 16))
        order_fake = Faker("pt_BR")
        order_fake.seed_instance(int(batch_hash, 16))

        orders = []
        order_items = []
        cancelamentos = []

        for offset in range(n_orders):
            order_id = order_start + offset
            customer_id = batch_rng.randint(1, n_customers)
            order_date = run_date - timedelta(days=batch_rng.randint(0, 6))
            status = batch_rng.choices(["completo", "cancelado"], weights=[0.85, 0.15])[0]
            orders.append(
                {
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "order_date": order_date.isoformat(),
                    "status": status,
                }
            )

            for item_number in range(1, batch_rng.randint(1, 4) + 1):
                order_items.append(
                    {
                        "order_item_id": order_id * 10 + item_number,
                        "order_id": order_id,
                        "product_id": batch_rng.randint(1, n_products),
                        "quantity": batch_rng.randint(1, 3),
                    }
                )

            if status == "cancelado":
                days_since_order = (run_date - order_date).days
                cancelamentos.append(
                    {
                        "order_id": order_id,
                        "cancel_reason": order_fake.sentence(nb_words=4),
                        "cancel_date": (
                            order_date + timedelta(days=batch_rng.randint(0, days_since_order))
                        ).isoformat(),
                    }
                )

        pd.DataFrame(orders, columns=["order_id", "customer_id", "order_date", "status"]).to_csv(
            batch_path / "orders.csv", index=False
        )
        pd.DataFrame(
            order_items, columns=["order_item_id", "order_id", "product_id", "quantity"]
        ).to_csv(batch_path / "order_items.csv", index=False)
        pd.DataFrame(
            cancelamentos, columns=["order_id", "cancel_reason", "cancel_date"]
        ).to_csv(batch_path / "cancelamentos.csv", index=False)

        manifest = {
            "run_id": run_id,
            "run_date": run_date.isoformat(),
            "batch_key": batch_hash[:16],
            "counts": {"customers": len(customers), "products": len(products), "orders": len(orders), "order_items": len(order_items), "cancelamentos": len(cancelamentos)},
        }
        tmp_manifest = manifest_path.with_suffix(".tmp")
        tmp_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_manifest.replace(manifest_path)
        print(f"[NOVO] Lote gerado: {batch_path}")

    return batch_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera lote determinístico de dados de e-commerce")
    parser.add_argument("--run-id", required=True, help="run_id da DAG (estável em retries)")
    parser.add_argument("--run-date", required=True, help="Data do lote no formato YYYY-MM-DD")
    args = parser.parse_args()
    generate_batch(args.run_id, date.fromisoformat(args.run_date))


if __name__ == "__main__":
    main()
