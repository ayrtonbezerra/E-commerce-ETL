{{config(materialized='view')}}

WITH source as (
    SELECT
        *
    FROM {{source('ecommerce_raw', 'customers')}}
),

renamed as(
    SELECT
        id,
        LOWER(TRIM(name)) as name,
        LOWER(TRIM(email)) as email,
        CAST(signup_date AS DATE) as signup_date
    FROM source
)

SELECT
    *
FROM renamed
