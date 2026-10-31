SELECT
    product_id,
    name,
    category,
    price,
    cost,
    margin
FROM {{ref('stg_products')}}