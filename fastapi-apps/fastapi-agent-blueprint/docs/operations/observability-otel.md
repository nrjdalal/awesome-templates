# OpenTelemetry Tracing — Operations Recipe

This document covers how to enable and operate the OpenTelemetry (OTEL) tracing
pipeline for PydanticAI Agents in the fastapi-agent-blueprint.

> Langfuse OTLP/HTTP opt-in recipe is a separate
> doc at [`docs/operations/observability-langfuse.md`](observability-langfuse.md)
> — tracked in [#137](https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/137).

## What you get

When OTEL is enabled, every PydanticAI Agent invocation emits
[GenAI semantic convention](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
spans to your OTLP-compatible backend:

| Span attribute | Content |
|---|---|
| `gen_ai.request.model` | model name (e.g. `gpt-4o`) |
| `gen_ai.usage.input_tokens` | prompt token count |
| `gen_ai.usage.output_tokens` | completion token count |
| `gen_ai.request.messages` | request messages (opt-in, privacy-sensitive) |
| `gen_ai.response.text` | completion text (opt-in, privacy-sensitive) |

Spans are emitted for both the `classification` domain and the `docs` RAG domain.
The Taskiq worker emits traces under the `fastapi-agent-blueprint-worker` service name.

OTEL does **not** require the `[pydantic-ai]` extra to configure the TracerProvider,
but `Agent.instrument_all()` (the PydanticAI patch) only fires when both
`--extra otel` and `--extra pydantic-ai` are installed.

## Prerequisites

```bash
uv sync --extra otel --extra pydantic-ai
```

This adds `opentelemetry-api`, `opentelemetry-sdk`, and
`opentelemetry-exporter-otlp-proto-grpc` (gRPC, default port 4317).

## Quickstart: local Jaeger

Jaeger ships an all-in-one Docker image that accepts OTLP/gRPC on port 4317
and exposes a UI on port 16686.

```bash
# 1. Start Jaeger
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest

# 2. Boot the blueprint with OTEL enabled
OTEL_ENABLED=true \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
LLM_PROVIDER=openai \
LLM_API_KEY=sk-... \
make dev

# 3. Trigger a classification or RAG query
curl -X POST http://localhost:8001/api/classification \
  -H "Content-Type: application/json" \
  -d '{"text": "hello world"}'

# 4. Open the Jaeger UI and filter by service name
open http://localhost:16686
```

Filter by **Service = `fastapi-agent-blueprint-server`** to see traces.

## Grafana Tempo

Tempo accepts OTLP/gRPC by default on port 4317. No extra configuration is
needed — just point the endpoint at your Tempo instance:

```bash
OTEL_ENABLED=true \
OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317 \
make dev
```

Optionally override the service name:

```bash
OTEL_SERVICE_NAME=my-agent-service make dev
```

## Arize Phoenix (LLM-native)

[Arize Phoenix](https://phoenix.arize.com) is an OSS LLMOps tool that natively
understands GenAI semantic convention spans. Boot Phoenix locally:

```bash
pip install arize-phoenix
python -m phoenix.server.main &
# → listening on :6006 (UI) and :4317 (OTLP/gRPC)

OTEL_ENABLED=true \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
make dev
```

The Phoenix UI shows token usage, latency histograms, and input/output payloads
with no additional configuration.

## HTTP exporter swap

Some backends (e.g. Langfuse in its hosted mode) expose only the OTLP/HTTP
receiver on port 4318 with path `/v1/traces`, not the gRPC receiver.

To switch, install the HTTP exporter package and replace the import in
`src/_core/infrastructure/observability/otel_setup.py`:

```bash
uv add opentelemetry-exporter-otlp-proto-http
```

In `otel_setup.py`, change:

```python
# From (gRPC — default):
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# To (HTTP):
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
```

Then set the HTTP endpoint:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

This is a one-line code swap, not a config flag, because the package and class
names differ between the two transports.

## Service name override

By default:
- The FastAPI server reports as `fastapi-agent-blueprint-server`
- The Taskiq worker reports as `fastapi-agent-blueprint-worker`

To override in your deployment:

```bash
OTEL_SERVICE_NAME=your-service-name make dev
```

The `OTEL_RESOURCE_ATTRIBUTES=service.name=foo` env var also works (OTel SDK
standard). Both take precedence over the blueprint default.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Bootstrap log `otel_extra_not_installed` (warning) | `--extra otel` not installed | `uv sync --extra otel` |
| No spans in backend | `OTEL_ENABLED=false` (default) | Set `OTEL_ENABLED=true` |
| No spans, no error | Wrong service name filter in UI | Filter by `fastapi-agent-blueprint-server` |
| gRPC connection refused | Wrong port (HTTP 4318 vs gRPC 4317) | Match port to backend receiver type |
| `otel_pydantic_ai_instrumentation_skipped` | `--extra pydantic-ai` not installed | `uv sync --extra pydantic-ai` |
| Validation error on boot | `OTEL_ENABLED=true` but no endpoint | Set `OTEL_EXPORTER_OTLP_ENDPOINT` |
