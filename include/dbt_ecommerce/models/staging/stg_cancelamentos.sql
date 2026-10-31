{{config(materialized='view')}}

WITH source as (
    SELECT
        *
    FROM {{ref('cancelamentos')}}
),

renamed as(
    SELECT
        order_id,
        LOWER(TRIM(cancel_reason)) as cancel_reason,
        CAST(cancel_date AS DATE) as cancel_date
    FROM source
)

SELECT
    *
FROM renamed