
{{ config(materialized='view') }}

WITH customer_activity AS (

    SELECT
        c.id AS customer_id,

        COUNT(o.order_id) FILTER (
            WHERE o.status = 'completo'
        ) AS total_orders,

        MIN(o.order_date) FILTER (
            WHERE o.status = 'completo'
        ) AS first_order,

        MAX(o.order_date) FILTER (
            WHERE o.status = 'completo'
        ) AS last_order,

        COUNT(o.order_id) FILTER (
            WHERE o.status = 'cancelado'
        ) AS total_cancels

    FROM {{ ref('stg_customers') }} c

    LEFT JOIN {{ ref('stg_orders') }} o
        ON c.id = o.customer_id

    GROUP BY c.id

)

SELECT
    customer_id,
    total_orders,
    first_order,
    last_order,
    last_order - first_order AS days_between,
    total_cancels,

    CASE
        WHEN last_order IS NOT NULL
         AND CURRENT_DATE - last_order > 90
        THEN 1
        ELSE 0
    END AS is_churn

FROM customer_activity