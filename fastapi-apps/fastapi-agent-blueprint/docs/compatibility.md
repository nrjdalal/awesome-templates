# Compatibility Matrix

## Runtime requirements

| Component | Minimum | Tested |
|---|---|---|
| Python | 3.12.9 | 3.12.9 |
| FastAPI | 0.115.12 | 0.128.0 |
| Pydantic | 2.10 | 2.12.5 |
| SQLAlchemy | 2.0.40 | 2.0.45 |
| Alembic | 1.15.2 | 1.17.2 |
| Taskiq | 0.12.1 | 0.12.1 |
| NiceGUI (`admin` extra) | 3.5.0 | 3.9.0 |
| structlog | 25.0.0 | 25.5.0 |
| dependency-injector | 4.46.0 | 4.48.3 |
| pydantic-settings | 2.10.1 | 2.12.0 |

## AI tool support

| Tool | Minimum | Tested | Notes |
|---|---|---|---|
| Claude Code | 2.0.0 | 2.1.132 | Skills use `SKILL.md` frontmatter |
| Codex CLI | 0.125.0 | 0.125.0 | Skills use YAML frontmatter; `codex exec` for non-interactive |

Skills are tested against the versions in the "Tested" column. Older versions may work but are not validated. If a skill breaks after a tool upgrade, open an issue.

## Database backends

| Backend | Status | Notes |
|---|---|---|
| SQLite | Verified | Default for quickstart and tests; no external infra required |
| PostgreSQL 14+ | Verified | Required for `make dev`; tested via `make test-pg` |
| MySQL 8+ | Supported | `DATABASE_ENGINE=mysql`; not in CI |
| DynamoDB | Verified | `make test-dynamo` requires DynamoDB Local container |

## Message brokers

| Broker | Status | Notes |
|---|---|---|
| InMemory (Taskiq) | Verified | Default for quickstart |
| SQS | Supported | Requires `sqs` extra + AWS credentials |
| RabbitMQ | Supported | Requires `rabbitmq` extra + running broker |

## Object storage

| Backend | Status | Notes |
|---|---|---|
| MinIO | Verified | Local dev via `docker-compose.local.yml` |
| AWS S3 | Supported | `STORAGE_TYPE=s3` + AWS credentials |

## AI / LLM providers (via PydanticAI)

| Provider | Status | Extra required | Notes |
|---|---|---|---|
| Stub (no real LLM) | Verified | — | Default for quickstart; keyword bag-of-words embedder |
| OpenAI | Supported | `pydantic-ai` | `EMBEDDING_PROVIDER=openai`, `LLM_PROVIDER=openai` |
| Anthropic | Supported | `pydantic-ai-anthropic` | `LLM_PROVIDER=anthropic` |
| AWS Bedrock | Supported | `pydantic-ai` + `aws` | `LLM_PROVIDER=bedrock` |
| Google | Supported | `pydantic-ai-google` | `LLM_PROVIDER=google` |
| Ollama | Supported | `pydantic-ai` | Local inference |

## Operating systems

| OS | Status | Notes |
|---|---|---|
| macOS (Apple Silicon / Intel) | Verified | Primary development platform |
| Linux (Ubuntu 22.04+, Debian 12+) | Verified | CI runs on `ubuntu-latest` |
| Windows (WSL2) | Best-effort | POSIX hooks require WSL2; native Windows not supported |
| Windows (native) | Not supported | Pre-commit hooks use POSIX shell; contributions welcome |

## Python version policy

Only Python 3.12+ is supported. The blueprint uses `match` statements, `TypeVar` with upper bounds (PEP 695-adjacent), and Pydantic v2 discriminated unions that require 3.12 behavior.

Python 3.13 is expected to work but is not yet in CI. Open an issue if you hit a 3.13-specific problem.

## Upgrading

See [CHANGELOG.md](../CHANGELOG.md) for version-by-version changes and migration notes. The `[0.x]` series follows FastAPI's convention: MINOR bumps may include breaking changes with a documented migration path.
