{{config(materialized='view')}}

WITH source as (
    SELECT
        *
    FROM {{ref('products')}}
),

renamed as(
    SELECT
        product_id,
        LOWER(TRIM(name)) as name,
        LOWER(TRIM(category)) as category,
        CAST(price AS NUMERIC) as price,
        CAST(COST as NUMERIC) as cost,
        ROUND(CAST(price - cost AS NUMERIC), 2) as margin
    FROM source
)

SELECT
    *
FROM renamed