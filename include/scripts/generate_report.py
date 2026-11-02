import argparse
import hashlib
import os
from datetime import timedelta
from pathlib import Path

import psycopg
import requests
from dotenv import load_dotenv
from psycopg.rows import dict_row

from load_data import get_connection_config

load_dotenv()


def get_report_data() -> dict:
    with psycopg.connect(
        **get_connection_config(),
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT
                    CURRENT_DATE AS report_date,
                    COUNT(*) AS registered_customers,
                    COUNT(*) FILTER (
                        WHERE last_order IS NOT NULL
                    ) AS past_buyers,
                    COUNT(*) FILTER (
                        WHERE is_churn = 1
                    ) AS churned,
                    COUNT(*) FILTER (
                        WHERE CURRENT_DATE - last_order
                        BETWEEN 61 AND 90
                    ) AS at_risk
                FROM analytics.int_churn_prediction_data
            """)
            retention = cur.fetchone()

            cur.execute("""
                SELECT
                    COUNT(*) FILTER (
                        WHERE order_date
                        BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE
                    ) AS orders_this_week,

                    COUNT(*) FILTER (
                        WHERE order_date
                        BETWEEN CURRENT_DATE - 13 AND CURRENT_DATE - 7
                    ) AS orders_last_week,

                    COUNT(*) FILTER (
                        WHERE status = 'cancelado'
                        AND order_date
                        BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE
                    ) AS cancellations,

                    COUNT(DISTINCT customer_id) FILTER (
                        WHERE status = 'completo'
                        AND order_date
                        BETWEEN CURRENT_DATE - 6 AND CURRENT_DATE
                    ) AS buying_customers

                FROM analytics.stg_orders
            """)
            activity = cur.fetchone()

            cur.execute("""
                SELECT
                    week_end,
                    past_buyers,
                    churned,
                    at_risk,
                    active
                FROM analytics.int_weekly_retention
                ORDER BY week_end DESC
                LIMIT 8
            """)
            trend = list(reversed(cur.fetchall()))

            cur.execute("""
                SELECT
                    customer_id,
                    total_orders,
                    CURRENT_DATE - last_order AS inactive_days
                FROM analytics.int_churn_prediction_data
                WHERE CURRENT_DATE - last_order BETWEEN 61 AND 90
                ORDER BY
                    total_orders DESC,
                    inactive_days DESC,
                    customer_id
                LIMIT 5
            """)
            opportunities = cur.fetchall()

    return {
        **retention,
        **activity,
        "trend": trend,
        "opportunities": opportunities,
    }


def pct(numerator: int, denominator: int) -> str:
    if not denominator:
        return "N/A"
    return f"{100 * numerator / denominator:.1f}%"


def weekly_change(current: int, previous: int) -> str:
    if not previous:
        return "N/A"
    return f"{(current - previous) * 100 / previous:+.1f}%"


def render_markdown(data: dict) -> str:
    day = data["report_date"]
    start = day - timedelta(days=6)

    trend_rows = "\n".join(
        f"| {r['week_end']:%Y-%m-%d} | {r['active']} | "
        f"{r['at_risk']} | {r['churned']} | "
        f"{pct(r['churned'], r['past_buyers'])} |"
        for r in data["trend"]
    )

    if data["opportunities"]:
        candidates = "\n".join(
            f"| {c['customer_id']} | {c['inactive_days']} | "
            f"{c['total_orders']} |"
            for c in data["opportunities"]
        )
    else:
        candidates = "| — | — | — |"

    return f"""# Weekly Customer Retention Report

**Period:** {start:%Y-%m-%d} to {day:%Y-%m-%d}  
**Data:** Synthetic e-commerce transactions

## Retention snapshot

| Metric | Value |
|---|---:|
| Registered customers | {data['registered_customers']} |
| Customers with completed orders | {data['past_buyers']} |
| Churned (>90 days inactive) | {data['churned']} |
| Churned buyer share | {pct(data['churned'], data['past_buyers'])} |
| At risk (61–90 days inactive) | {data['at_risk']} |

## Weekly order activity

| Metric | Value |
|---|---:|
| Orders placed | {data['orders_this_week']} |
| Change vs. previous 7 days | {weekly_change(data['orders_this_week'], data['orders_last_week'])} |
| Customers with completed orders | {data['buying_customers']} |
| Canceled orders | {data['cancellations']} |
| Order cancellation rate | {pct(data['cancellations'], data['orders_this_week'])} |

## Retention trend (weekly snapshots)

| As of | Active | At risk | Churned | Churned buyer share |
|---|---:|---:|---:|---:|
{trend_rows}

## Customers to prioritize for reactivation

| Customer ID | Days since last completed order | Completed orders |
|---|---:|---:|
{candidates}

### Definitions

- **Active:** a completed purchase within the past 60 days.
- **At risk:** 61–90 days since the most recent completed purchase.
- **Churned:** more than 90 days since the most recent completed purchase.
- **Churned buyer share:** currently churned customers divided by customers with at least one completed purchase.
- Weekly snapshots are reconstructed from dated transactions.
- **This is an inactivity-based churn proxy, not a predictive ML model.**
"""


def render_telegram(data: dict) -> str:
    day = data["report_date"]

    previous = (
        data["trend"][-2]
        if len(data["trend"]) >= 2
        else None
    )

    if previous:
        change = data["churned"] - previous["churned"]
        churn_change = f"{change:+d}"
    else:
        churn_change = "N/A"

    active = (
        data["past_buyers"]
        - data["churned"]
        - data["at_risk"]
    )

    top_customers = "\n".join(
        f"• #{c['customer_id']}: "
        f"{c['inactive_days']} days inactive, "
        f"{c['total_orders']} completed orders"
        for c in data["opportunities"][:3]
    ) or "No at-risk customers."

    return (
        f"<b>Weekly Customer Retention</b>\n"
        f"{day:%Y-%m-%d}\n\n"

        "<b>Customer health</b>\n"
        f"Active: {active}\n"
        f"At risk: {data['at_risk']}\n"
        f"Churned: {data['churned']} "
        f"({pct(data['churned'], data['past_buyers'])})\n"
        f"Change in churned customers vs. 7 days ago: "
        f"{churn_change}\n\n"

        "<b>Last 7 days</b>\n"
        f"Orders: {data['orders_this_week']} "
        f"({weekly_change(data['orders_this_week'], data['orders_last_week'])} "
        "vs. previous week)\n"
        f"Buying customers: {data['buying_customers']}\n"
        f"Cancellations: {data['cancellations']}\n\n"

        "<b>Reactivation candidates</b>\n"
        f"{top_customers}\n\n"

        "<i>Churn = over 90 days without a completed "
        "purchase. Synthetic data.</i>"
    )


def save_report(run_id: str, content: str) -> Path:
    root = Path(os.environ["OUTPUT_PATH"]).parent / "reports"
    root.mkdir(parents=True, exist_ok=True)

    key = hashlib.sha256(run_id.encode()).hexdigest()[:16]

    batch_path = root / "batches" / f"{key}.md"
    batch_path.parent.mkdir(parents=True, exist_ok=True)
    batch_path.write_text(content, encoding="utf-8")

    latest_path = root / "latest_report.md"
    latest_path.write_text(content, encoding="utf-8")

    return latest_path


def send_telegram(message: str) -> None:
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token and not chat_id:
        print("[REPORT] Telegram not configured; Markdown report saved.")
        return

    if not token or not chat_id:
        raise ValueError(
            "Configure both TELEGRAM_TOKEN and TELEGRAM_CHAT_ID, "
            "or neither."
        )

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
            },
            timeout=20,
        )
        response.raise_for_status()

        if not response.json().get("ok"):
            raise RuntimeError("Telegram API returned ok=false")

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Telegram API request failed: {type(exc).__name__}"
        ) from None

    print("[REPORT] Telegram message sent")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    data = get_report_data()
    path = save_report(args.run_id, render_markdown(data))

    print(f"[REPORT] Saved: {path}")
    send_telegram(render_telegram(data))


if __name__ == "__main__":
    main()