SELECT
    product_id,
    price,
    cost
FROM {{ ref('stg_products') }}
WHERE price <= 0
   OR cost < 0