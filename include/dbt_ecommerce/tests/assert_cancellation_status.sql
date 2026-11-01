SELECT
    c.order_id,
    o.status
FROM {{ ref('stg_cancelamentos') }} c
INNER JOIN {{ ref('stg_orders') }} o
    ON c.order_id = o.order_id
WHERE o.status <> 'cancelado'