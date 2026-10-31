from tracemalloc import start

import pandas as pd
from faker import Faker
import random
import os
from dotenv import load_dotenv
from pathlib import Path
from datetime import timedelta

load_dotenv()

# Instanciando gerador de dados
fake = Faker()

random.seed(42)

# Definição de variuáveis
## número de clientes, produtos e pedidos
N_CUSTOMERS = int(os.getenv('N_CUSTOMERS'))
N_PRODUCTS = int(os.getenv('N_PRODUCTS'))
N_ORDERS = int(os.getenv('N_ORDERS'))
OUTPUT_PATH = Path(os.getenv('OUTPUT_PATH'))
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

#-------------------- 1. Clientes --------------------

customers = []
for id in range(1, N_CUSTOMERS+1):
    customers.append(
        {
            'id': id,
            'name': fake.name(),
            'email': fake.email(),
            'signup_date': fake.date_between(start_date = '-2y', end_date='today')
        }
    )

df_customers = pd.DataFrame(customers)

df_customers.to_csv(OUTPUT_PATH/'customers.csv', index=False)


#-------------------- 2. Produtos --------------------

categorias = ['Eletrônicos', 'Roupas', 'Livros', 'Esportes', 'Beleza']

products = []

for prod_id in range(1, N_PRODUCTS+1):
    categoria = random.choice(categorias)
    custo = round(random.uniform(1, 100), 2)
    preco = round(custo * random.uniform(1.2, 2.5), 2)
    products.append(
        {
            'product_id': prod_id,
            'name': fake.word().capitalize() + " " + fake.word().capitalize(),
            'category': categoria,
            'cost': custo,
            'price': preco
        }
    )

df_products = pd.DataFrame(products)

df_products.to_csv(OUTPUT_PATH/'products.csv', index=False)

#-------------------- 3. Pedidos --------------------

orders = []
order_items = []

for i in range(N_ORDERS):
    customer_id = random.randint(1, N_CUSTOMERS)
    order_date = fake.date_between(start_date='-1y', end_date='today')
    status = random.choices(['completo', 'cancelado'], weights=[0.85, 0.15])[0]

    orders.append(
        {
            'order_id': i,
            'customer_id': customer_id,
            'order_date': order_date,
            'status': status
        }
    )

    n_itens = random.randint(1, 4)

    for _ in range(n_itens):
        product_id = random.randint(1, N_PRODUCTS)
        quantity = random.randint(1, 3)
        order_items.append(
            {
                'order_id': i,
                'product_id': product_id,
                'quantity': quantity
            }
        )

df_orders = pd.DataFrame(orders)
df_orders.to_csv(OUTPUT_PATH/'orders.csv', index = False)

df_order_items = pd.DataFrame(order_items)
df_order_items.to_csv(OUTPUT_PATH/'order_items.csv', index=False)

#-------------------- 4. Cancelamentos --------------------

cancelamentos = df_orders[df_orders['status'] == 'cancelado'].copy()

cancelamentos['cancel_reason'] = [fake.sentence(nb_words=4) for _ in range(cancelamentos.shape[0])]
cancelamentos['cancel_date'] = cancelamentos['order_date'].apply(lambda x: x + timedelta(days=random.randint(1, 3)))

df_canc = cancelamentos[['order_id', 'cancel_reason', 'cancel_date']]
df_canc.to_csv(OUTPUT_PATH/'cancelamentos.csv', index=False)

print(f'Dados gerados em {OUTPUT_PATH.resolve()}')