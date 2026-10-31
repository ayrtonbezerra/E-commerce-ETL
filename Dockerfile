FROM astrocrpublic.azurecr.io/runtime:3.3-11

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

RUN uv python install 3.11.9 \
    && uv venv --python 3.11.9 /usr/local/airflow/dbt_venv \
    && uv pip install \
       --python /usr/local/airflow/dbt_venv/bin/python \
       "dbt-core==1.9.0" \
       "dbt-postgres==1.9.0"

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

USER astro