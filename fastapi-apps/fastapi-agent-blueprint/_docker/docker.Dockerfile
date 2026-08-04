# syntax=docker/dockerfile:1
#
# Multi-stage image for the server, worker and scheduler processes. All three
# share one image and differ only in the command compose (or your orchestrator)
# gives them — see docker-compose.yml.
#
# Previously this was a single stage that did `COPY _env/${ENV}.env /app/.env`
# with `ARG ENV=prod`. Only *.env.example files are committed and `_env/*.env`
# is gitignored, so the image did not build as shipped:
#
#   ERROR: failed to compute cache key: "/_env/prod.env": not found
#
# and making it build by adding that file bakes credentials into a layer that
# `docker history` will happily print. Configuration now comes from the process
# environment at run time, which compose `env_file` and every orchestrator's
# secret mechanism already provide.

# ── builder ──────────────────────────────────────────────────────────────────
# build-essential compiles any sdist-only wheels. It stays in this stage: the
# previous single-stage build shipped the whole toolchain in the final image.
FROM python:3.12-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Broker extras are not optional for the environment this image targets:
# Settings requires an explicit BROKER_TYPE in stg/prod, and both supported
# values need a package a core-only `uv sync` does not install
# (sqs -> taskiq-aws, rabbitmq -> taskiq-aio-pika). Override to trim or extend,
# e.g. --build-arg EXTRAS="--extra rabbitmq --extra admin".
ARG EXTRAS="--extra sqs --extra rabbitmq"

COPY pyproject.toml uv.lock /app/
RUN uv sync --no-dev --frozen --no-install-project ${EXTRAS}

# ── runtime ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# Non-root. The previous image ran everything as root.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --no-create-home app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

# migrations/ and alembic.ini were never copied, so `alembic upgrade head` was
# impossible inside the container — the usual pre-start step for this stack.
COPY --chown=app:app src/ /app/src/
COPY --chown=app:app migrations/ /app/migrations/
COPY --chown=app:app alembic.ini /app/alembic.ini

USER app

EXPOSE 8000

# curl is absent from the slim base and installing it for a probe would add an
# apt layer, so use the interpreter that is already here.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

# No --env-file: configuration is read from the process environment.
CMD ["uvicorn", "src._apps.server.app:app", "--workers", "1", "--host", "0.0.0.0", "--port", "8000"]
