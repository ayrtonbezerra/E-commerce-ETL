WITH orders_completed AS (
    SELECT
        *
    FROM {{ref('stg_orders')}}
    WHERE status = 'completo'
),

items AS (
    SELECT
        *
    FROM {{ref('stg_order_items')}}
),

products AS (
    SELECT
        *
    FROM {{ref('stg_products')}}
),

joined AS (
    SELECT
        oc.order_id,
        oc.customer_id,
        oc.order_date,
        i.quantity,
        i.product_id,
        p.price,
        p.cost,
        p.margin,
        (p.price * i.quantity) as revenue,
        (i.quantity * p.margin) as profit

    FROM orders_completed oc
    INNER JOIN items i ON oc.order_id = i.order_id
    INNER JOIN products p ON i.product_id = p.product_id
)

SELECT
    *
FROM joined