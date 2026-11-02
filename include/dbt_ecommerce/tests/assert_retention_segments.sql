SELECT
    week_end,
    past_buyers,
    active,
    at_risk,
    churned
FROM {{ ref('int_weekly_retention') }}
WHERE active + at_risk + churned <> past_buyers