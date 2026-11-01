SELECT
    order_item_id,
    order_id,
    quantity
FROM {{ ref('stg_order_items') }}
WHERE quantity <= 0
