import os
from dotenv import load_dotenv
import pandas as pd
import requests

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
DBT_DIR = os.getenv('OUTPUT_PATH')

def render_retport_text():
    df_sales = pd.read_csv(f'{DBT_DIR}/orders.csv')
    df_products = pd.read_csv(f'{DBT_DIR}/products.csv')

    total_pedidos = df_sales.shape[0]

    total_cancelamentos = df_sales[df_sales['status'] == 'cancelado'].shape[0]

    taxa_cancelamentos = round(total_cancelamentos/total_pedidos, 2) * 100

    top_produto = df_products.sort_values(by='price', ascending=False).iloc[0]['name']

    message = (
        "*Relatório Semanal - E-commerce*\n\n"
        f"• Total de pedidos: *{total_pedidos}*\n"
        f"• Pedidos cancelados: *{total_cancelamentos}*\n"
        f"• Taxa de cancelamento: *{taxa_cancelamentos}%*\n"
        f"• Produto mais caro: *{top_produto}*\n"
    )

    return message

def send_report(message:str):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'

    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }

    response = requests.post(
        url = url,
        data = payload
    )

    if response.status_code != 200:
        print(f'Erro para enviar mensagem:\nCódigo: {response.status_code}\nMensagem: {response.text}')
        response.raise_for_status()
    else:
        print('Relatório enviado.')

def notify_telegram_weekly_report():
    report_message = render_retport_text()
    send_report(report_message)

if __name__ == '__main__':
    notify_telegram_weekly_report()