# Langfuse Tracing — Operations Recipe

This document covers the opt-in Langfuse recipe for receiving PydanticAI
OpenTelemetry traces from the fastapi-agent-blueprint.

Langfuse is not part of `make quickstart` or the base Docker Compose file. Use
this stack only when a team wants the Langfuse UI on top of the existing OTEL
trace path.

This Compose recipe is local-development infrastructure. It publishes host
ports on `127.0.0.1` and expects local-only secrets in `_env/langfuse.env`; do
not reuse it as a production deployment manifest.

GenAI spans may include prompts, input/output messages, and system
instructions. Before enabling OTEL traces in a production-like environment,
decide who can access the trace backend and how long trace payloads are
retained.

## What you get

With the OTEL core enabled, Langfuse can display the GenAI spans emitted by
PydanticAI:

| Span data | Available through OTLP |
|---|---|
| Token usage | Yes |
| Latency | Yes |
| Input/output messages | Yes, when emitted by the instrumented agent |
| System instructions | Yes, when emitted by the instrumented agent |

## What this recipe does not deliver

This recipe is OTLP trace ingestion only. The following Langfuse-native features
remain out of scope and require a later SDK/API or custom span-processor issue:

- Prompt version to trace linkage
- Evaluation scores and dataset regression tests
- A/B prompt label analysis
- Live prompt editing with trace feedback

## Prerequisites

Install the OTEL and PydanticAI extras:

```bash
uv sync --extra otel --extra pydantic-ai
```

The application currently uses the OTLP gRPC exporter by default. Langfuse OTLP
ingestion uses HTTP/protobuf, so follow the HTTP exporter swap below before
pointing the app at this recipe.

> Important: complete the HTTP exporter swap before booting the app with the
> Langfuse endpoint. A gRPC exporter cannot send traces to
> `http://localhost:4318/v1/traces`.

## HTTP exporter swap

Langfuse receives OTLP over HTTP/protobuf. The local recipe exposes
`localhost:4318` through an OpenTelemetry Collector, and the collector forwards
traces to the Langfuse web ingestion endpoint at
`/api/public/otel`.

Install the HTTP exporter package:

```bash
uv add opentelemetry-exporter-otlp-proto-http
```

`uv add` modifies `pyproject.toml` and `uv.lock`. Treat that as a local recipe
step unless this project later adds HTTP/protobuf support to the committed
`otel` extra. If you later switch back to the gRPC-only Jaeger or Tempo recipes in
[`observability-otel.md`](observability-otel.md), revert the import below or add
a protocol toggle in a follow-up change.

Then change `src/_core/infrastructure/observability/otel_setup.py`:

```python
# From (gRPC):
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# To (HTTP/protobuf):
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
```

## Start Langfuse

```bash
make observability-langfuse
```

On first run, `make observability-langfuse` creates `_env/langfuse.env` with
random local secrets and then starts the stack with `docker compose --env-file`.
The generated file is ignored by git. To create the file without starting
containers, run:

```bash
make langfuse-env
```

The stack starts these local ports:

| Service | Local URL |
|---|---|
| Langfuse web | `http://localhost:3000` |
| OTLP/HTTP collector | `http://localhost:4318/v1/traces` |
| PostgreSQL | `localhost:5433` |
| Redis | `localhost:6380` |
| MinIO S3 API | `http://localhost:9090` |
| MinIO console | `http://localhost:9091` |

ClickHouse is internal to the Compose network and is not published to the host.

The generated bootstrap credentials are for local development only:

| Credential | Source |
|---|---|
| Login email | `LANGFUSE_INIT_USER_EMAIL` in `_env/langfuse.env` |
| Login password | `LANGFUSE_INIT_USER_PASSWORD` in `_env/langfuse.env` |
| Project public key | `LANGFUSE_INIT_PROJECT_PUBLIC_KEY` in `_env/langfuse.env` |
| Project secret key | `LANGFUSE_INIT_PROJECT_SECRET_KEY` in `_env/langfuse.env` |

For production-like testing, replace every generated secret in
`_env/langfuse.env` before starting the stack. The Compose file intentionally
requires secret environment variables instead of carrying checked-in defaults.

Set the HTTP traces endpoint:

```bash
OTEL_ENABLED=true \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces \
LLM_PROVIDER=openai \
LLM_API_KEY=sk-... \
make dev
```

If you override `LANGFUSE_INIT_PROJECT_PUBLIC_KEY` or
`LANGFUSE_INIT_PROJECT_SECRET_KEY`, also set `LANGFUSE_OTEL_BASIC_AUTH` to the
base64 value of `public_key:secret_key` in `_env/langfuse.env` before running
`make observability-langfuse`:

```bash
printf %s 'pk-lf-your-key:sk-lf-your-key' | base64
```

If this value does not match the bootstrapped project keys, the collector
exporter will receive HTTP 401 responses from Langfuse.

## Verify the first trace

1. Open `http://localhost:3000` and log in with the local bootstrap user.
2. Start the app with `OTEL_ENABLED=true` and
   `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces`.
3. Trigger a classification or RAG request against the running API.
4. In Langfuse, open the local project and check the Traces view.

The first trace should show the blueprint service name plus GenAI span data such
as token usage, latency, messages, and system instructions when those attributes
are emitted by PydanticAI.

## Stop Langfuse

```bash
make observability-langfuse-down
```

This stops the containers but keeps named volumes. Remove volumes manually only
when you want to discard the local Langfuse data.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No traces in Langfuse | App is still using the gRPC exporter | Apply the HTTP exporter swap |
| HTTP 401 from collector exporter | Collector auth header does not match project keys | Recompute `LANGFUSE_OTEL_BASIC_AUTH` |
| App validation error on boot | `OTEL_ENABLED=true` without endpoint | Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces` |
| Port collision on `3000`, `4318`, `5433`, `6380`, or `9090` | Another local service is using the port | Stop the other service or override the Compose port mapping locally |
| Langfuse web is slow on first boot | Migrations and ClickHouse initialization are still running | Wait for `docker compose -f docker-compose.langfuse.yml ps` to show healthy services |
