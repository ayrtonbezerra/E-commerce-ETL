{{ config(materialized='view') }}

WITH weeks AS (

    SELECT
        (CURRENT_DATE - week_offset * 7)::date AS week_end

    FROM generate_series(0, 7) AS offsets(week_offset)

),

weekly_last_purchases AS (

    SELECT
        w.week_end,
        c.id AS customer_id,
        MAX(o.order_date) AS last_order

    FROM weeks w

    INNER JOIN {{ ref('stg_customers') }} c
        ON c.signup_date <= w.week_end

    LEFT JOIN {{ ref('stg_orders') }} o
        ON o.customer_id = c.id
        AND o.status = 'completo'
        AND o.order_date <= w.week_end

    GROUP BY
        w.week_end,
        c.id

)

SELECT
    week_end,

    COUNT(*) FILTER (
        WHERE last_order IS NOT NULL
    ) AS past_buyers,

    COUNT(*) FILTER (
        WHERE last_order IS NOT NULL
          AND week_end - last_order BETWEEN 0 AND 60
    ) AS active,

    COUNT(*) FILTER (
        WHERE last_order IS NOT NULL
          AND week_end - last_order BETWEEN 61 AND 90
    ) AS at_risk,

    COUNT(*) FILTER (
        WHERE last_order IS NOT NULL
          AND week_end - last_order > 90
    ) AS churned,

    COUNT(*) FILTER (
        WHERE last_order IS NULL
    ) AS never_purchased

FROM weekly_last_purchases

GROUP BY week_end