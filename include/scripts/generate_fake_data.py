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
        raise ValueError("Invalid N_CUSTOMERS, N_PRODUCTS or N_ORDERS")

    if n_customers >= 1_000_000:
        raise ValueError("N_CUSTOMERS must be below 1,000,000")

    return output_path, n_customers, n_products, n_orders


def generate_batch(
    run_id: str,
    run_date: date,
    mode: str = "incremental",
) -> Path:
    if not run_id.strip() or mode not in {"incremental", "history"}:
        raise ValueError("Invalid run_id or mode")

    output_path, n_customers, n_products, n_orders = get_settings()

    batch_hash = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    batch_path = output_path / "batches" / batch_hash[:16]
    manifest_path = batch_path / "manifest.json"

    batch_path.mkdir(parents=True, exist_ok=True)

    # Reuse completed batches instead of generating new records.
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        if (
            manifest.get("run_id") != run_id
            or manifest.get("mode", "incremental") != mode
        ):
            raise ValueError("Manifest does not match the requested batch")

        # Historical data is anchored to its first generation date.
        if mode == "incremental" and manifest["run_date"] != run_date.isoformat():
            raise ValueError("run_date differs from the existing batch")

        for name in CSV_NAMES:
            if not (batch_path / f"{name}.csv").is_file():
                raise FileNotFoundError(f"Missing CSV: {name}")

        print(f"[REPLAY] Existing batch: {batch_path}")
        return batch_path

    rng = random.Random(int(batch_hash, 16))
    batch_number = int(batch_hash[:10], 16) + 1
    order_start = batch_number * ORDER_ID_STRIDE

    # Stable product catalog shared by historical and weekly batches.
    product_fake = Faker("pt_BR")
    product_fake.seed_instance(43)
    product_rng = random.Random(43)

    products = []

    for product_id in range(1, n_products + 1):
        cost = round(product_rng.uniform(1, 100), 2)

        products.append({
            "product_id": product_id,
            "name": (
                f"{product_fake.word().capitalize()} "
                f"{product_fake.word().capitalize()}"
            ),
            "category": product_rng.choice(CATEGORIES),
            "cost": cost,
            "price": round(cost * product_rng.uniform(1.2, 2.5), 2),
        })

    orders = []
    order_items = []
    cancellations = []

    order_fake = Faker("pt_BR")
    order_fake.seed_instance(int(batch_hash, 16))

    if mode == "history":
        # Historical customers use a separate ID range, so we can
        # bootstrap an existing database without overwriting customers.
        history_count = max(30, n_customers)

        if history_count * 3 > ORDER_ID_STRIDE:
            raise ValueError("Historical batch exceeds order ID capacity")

        customer_ids = list(
            range(1_000_001, 1_000_001 + history_count)
        )

        customer_fake = Faker("pt_BR")
        customer_fake.seed_instance(123)

        customers = [
            {
                "id": cid,
                "name": customer_fake.name(),
                "email": f"historical_{cid}@example.com",
                "signup_date": (
                    run_date - timedelta(days=420 + rng.randint(0, 100))
                ).isoformat(),
            }
            for cid in customer_ids
        ]

        rng.shuffle(customer_ids)

        churn_end = int(history_count * 0.45)
        risk_end = churn_end + int(history_count * 0.35)

        for index, customer_id in enumerate(customer_ids):
            if index < churn_end:
                inactive_days = rng.randint(110, 170)
            elif index < risk_end:
                inactive_days = rng.randint(65, 85)
            else:
                inactive_days = rng.randint(7, 35)

            # Most recent completed order determines customer status.
            order_ages = [inactive_days]

            if rng.random() < 0.65:
                order_ages.append(
                    inactive_days + rng.randint(35, 90)
                )

            if rng.random() < 0.25:
                order_ages.append(
                    inactive_days + rng.randint(95, 160)
                )

            for days in sorted(order_ages, reverse=True):
                order_id = order_start + len(orders)
                order_date = run_date - timedelta(days=days)

                # Ensure the most recent historical order is completed.
                if days == inactive_days:
                    status = "completo"
                else:
                    status = rng.choices(
                        ["completo", "cancelado"],
                        weights=[0.85, 0.15],
                    )[0]

                orders.append({
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "order_date": order_date.isoformat(),
                    "status": status,
                })

                for item_number in range(1, rng.randint(1, 4) + 1):
                    order_items.append({
                        "order_item_id": order_id * 10 + item_number,
                        "order_id": order_id,
                        "product_id": rng.randint(1, n_products),
                        "quantity": rng.randint(1, 3),
                    })

                if status == "cancelado":
                    cancellations.append({
                        "order_id": order_id,
                        "cancel_reason": order_fake.sentence(nb_words=4),
                        "cancel_date": (
                            order_date + timedelta(days=rng.randint(0, 3))
                        ).isoformat(),
                    })

    else:
        # Existing incremental behavior: one new weekly batch.
        customer_fake = Faker("pt_BR")
        customer_fake.seed_instance(42)

        customer_rng = random.Random(42)
        signup_start = date(2024, 1, 1)

        customers = [
            {
                "id": cid,
                "name": customer_fake.name(),
                "email": customer_fake.email(),
                "signup_date": (
                    signup_start
                    + timedelta(days=customer_rng.randint(0, 365))
                ).isoformat(),
            }
            for cid in range(1, n_customers + 1)
        ]

        for offset in range(n_orders):
            order_id = order_start + offset
            order_date = run_date - timedelta(days=rng.randint(0, 6))

            status = rng.choices(
                ["completo", "cancelado"],
                weights=[0.85, 0.15],
            )[0]

            orders.append({
                "order_id": order_id,
                "customer_id": rng.randint(1, n_customers),
                "order_date": order_date.isoformat(),
                "status": status,
            })

            for item_number in range(1, rng.randint(1, 4) + 1):
                order_items.append({
                    "order_item_id": order_id * 10 + item_number,
                    "order_id": order_id,
                    "product_id": rng.randint(1, n_products),
                    "quantity": rng.randint(1, 3),
                })

            if status == "cancelado":
                cancellations.append({
                    "order_id": order_id,
                    "cancel_reason": order_fake.sentence(nb_words=4),
                    "cancel_date": (
                        order_date
                        + timedelta(
                            days=rng.randint(0, (run_date - order_date).days)
                        )
                    ).isoformat(),
                })

    datasets = {
        "customers": (
            customers,
            ["id", "name", "email", "signup_date"],
        ),
        "products": (
            products,
            ["product_id", "name", "category", "cost", "price"],
        ),
        "orders": (
            orders,
            ["order_id", "customer_id", "order_date", "status"],
        ),
        "order_items": (
            order_items,
            ["order_item_id", "order_id", "product_id", "quantity"],
        ),
        "cancelamentos": (
            cancellations,
            ["order_id", "cancel_reason", "cancel_date"],
        ),
    }

    for name, (records, columns) in datasets.items():
        pd.DataFrame(
            records, columns=columns
        ).to_csv(batch_path / f"{name}.csv", index=False)

    manifest = {
        "run_id": run_id,
        "run_date": run_date.isoformat(),
        "mode": mode,
        "batch_key": batch_hash[:16],
        "counts": {
            name: len(records)
            for name, (records, _) in datasets.items()
        },
    }

    temp_manifest = manifest_path.with_suffix(".tmp")
    temp_manifest.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    temp_manifest.replace(manifest_path)

    print(f"[NEW] {mode} batch: {batch_path}")
    return batch_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate reproducible e-commerce batches"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-date", required=True)
    parser.add_argument(
        "--mode",
        choices=["incremental", "history"],
        default="incremental",
    )

    args = parser.parse_args()

    generate_batch(
        args.run_id,
        date.fromisoformat(args.run_date),
        mode=args.mode,
    )


if __name__ == "__main__":
    main()