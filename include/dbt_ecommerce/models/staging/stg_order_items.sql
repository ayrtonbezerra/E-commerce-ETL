{{config(materialized='view')}}

WITH source as (
    SELECT
        *
    FROM {{source('ecommerce_raw', 'order_items')}}
),

renamed as(
    SELECT
        order_item_id,
        order_id,
        product_id,
        CAST(quantity AS NUMERIC) as quantity
    FROM source
)

SELECT
    *
FROM renamed