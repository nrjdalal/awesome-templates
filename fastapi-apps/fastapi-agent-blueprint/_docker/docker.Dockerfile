FROM python:3.12-slim-bookworm

ARG ENV=prod

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock /app/
RUN uv sync --no-dev --frozen

COPY src/ /app/src/
COPY _env/${ENV}.env /app/.env

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src._apps.server.app:app", "--workers", "1", "--host", "0.0.0.0", "--port", "8000", "--env-file", ".env"]
