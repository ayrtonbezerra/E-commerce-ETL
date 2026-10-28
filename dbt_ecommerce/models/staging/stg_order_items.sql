{{config(materialized='view')}}

WITH source as (
    SELECT
        *
    FROM {{ref('order_items')}}
),

renamed as(
    SELECT
        order_id,
        product_id,
        CAST(quantity AS NUMERIC) as quantity
    FROM source
)

SELECT
    *
FROM renamed