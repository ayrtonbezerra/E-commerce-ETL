{{config(materialized='view')}}

WITH source as (
    SELECT
        *
    FROM {{ref('orders')}}
),

renamed as(
    SELECT
        order_id,
        customer_id,
        CAST(order_date AS DATE) as order_date,
        LOWER(TRIM(status)) as status
    FROM source
)

SELECT
    *
FROM renamed