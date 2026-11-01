import os
import requests
import psycopg # type: ignore
from dotenv import load_dotenv
from load_data import get_connection_config

load_dotenv()


def render_report_text() -> str:
    with psycopg.connect(**get_connection_config()) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*), COUNT(*) FILTER (WHERE status = 'cancelado')
                FROM raw.orders
            """)
            total_orders, cancelled_orders = cur.fetchone()
            cur.execute("SELECT name FROM raw.products ORDER BY price DESC LIMIT 1")
            result = cur.fetchone()
            most_expensive = result[0] if result else "Sem produtos"

    rate = 100 * cancelled_orders / total_orders if total_orders else 0
    return (
        "*Resumo acumulado - E-commerce*\n\n"
        f"• Total de pedidos: *{total_orders}*\n"
        f"• Pedidos cancelados: *{cancelled_orders}*\n"
        f"• Taxa de cancelamento: *{rate:.2f}%*\n"
        f"• Produto mais caro: *{most_expensive}*\n"
    )


def send_report(message: str) -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
        timeout=30,
    )
    response.raise_for_status()
    print("Relatório enviado ao Telegram")


if __name__ == "__main__":
    send_report(render_report_text())