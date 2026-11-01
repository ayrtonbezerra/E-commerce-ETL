SELECT
    c.order_id,
    o.order_date,
    c.cancel_date
FROM {{ ref('stg_cancelamentos') }} c
INNER JOIN {{ ref('stg_orders') }} o
    ON c.order_id = o.order_id
WHERE c.cancel_date < o.order_date