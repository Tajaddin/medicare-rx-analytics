# Two images from one file:
#   pipeline  rx + dbt + the Bash extractor (curl); what would run against a real Snowflake account
#   emulator  the pipeline image plus fakesnow, the local Snowflake stand-in; never deployed
FROM python:3.12-slim-bookworm AS pipeline
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY scripts ./scripts
COPY dbt ./dbt
# The virtualenv stays root-owned (read-only for the app user); only the output folders are writable.
# (A chown -R of /app would copy the whole 1 GB environment into another layer.)
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev \
    && mkdir -p reports bi/exports data \
    && chown -R app:app reports bi/exports data dbt
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 DBT_PROFILES_DIR=/app/dbt
USER app
ENTRYPOINT ["rx"]
CMD ["--help"]

FROM pipeline AS emulator
USER root
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --extra emulator
USER app
EXPOSE 8085
# In memory only: fakesnow's server mode ignores -d, so restarting the container empties the warehouse.
ENTRYPOINT ["fakesnow"]
CMD ["-s", "-p", "8085", "--host", "0.0.0.0"]
