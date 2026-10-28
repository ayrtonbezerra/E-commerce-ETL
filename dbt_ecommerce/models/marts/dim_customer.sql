WITH base AS (
    SELECT
        *
    FROM {{ref('stg_customers')}}
),

churn_data AS (
    SELECT
        *
    FROM {{ref('int_churn_prediction_data')}}
)

SELECT
    b.id as id,
    b.name as name,
    b.email as email,
    c.total_orders as total_orders,
    c.total_cancels as total_cancels,
    c.is_churn as is_churn
FROM base b
LEFT JOIN churn_data c ON b.id = c.customer_id