import secrets
import warnings
from typing import Self

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

KNOWN_ENVS = ("quickstart", "local", "dev", "stg", "prod")
KNOWN_ENGINES = ("postgresql", "mysql", "sqlite")
KNOWN_BROKER_TYPES = ("sqs", "rabbitmq", "inmemory")
KNOWN_EMBEDDING_PROVIDERS = (
    "openai",
    "bedrock",
    "google",
    "ollama",
    "sentence-transformers",
)
KNOWN_STORAGE_TYPES = ("s3", "minio")
KNOWN_LLM_PROVIDERS = ("openai", "anthropic", "bedrock")
STRICT_ENVS = frozenset({"stg", "prod"})

_OPENAI_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}
_BEDROCK_DIMENSIONS: dict[str, int] = {
    "amazon.titan-embed-text-v2:0": 1024,
    "amazon.titan-embed-text-v1": 1536,
}
_GOOGLE_DIMENSIONS: dict[str, int] = {
    "gemini-embedding-001": 768,
    "text-embedding-004": 768,
    "text-multilingual-embedding-002": 768,
}
_LOCAL_DIMENSIONS: dict[str, int] = {
    "nomic-embed-text": 768,
    "all-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768,
}

_UNSAFE_DEFAULTS: dict[str, str] = {
    "admin_storage_secret": "change-me-in-production",  # noqa: S105
    "database_password": "postgres",  # noqa: S105
    "database_host": "localhost",
    "jwt_secret_key": "change-me-in-production",  # noqa: S105
}

_UNSAFE_JWT_SECRETS = frozenset(
    {
        "change-me",
        "change-me-in-production",
        "secret",
        "jwt-secret",
    }
)

_WARN_DEFAULTS: dict[str, str] = {
    "task_name_prefix": "my-project",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ----------------------------------------------------------------
    # General
    # ----------------------------------------------------------------
    # Environment (e.g. local, dev, stg, prod)
    env: str = Field(default="local", validation_alias=AliasChoices("ENV", "env"))

    # Taskiq task name prefix (e.g. "my-project.user.test")
    task_name_prefix: str = Field(
        default="my-project", validation_alias="TASK_NAME_PREFIX"
    )

    # ----------------------------------------------------------------
    # Admin Dashboard
    #
    # Authentication is backed by the auth domain. ADMIN_BOOTSTRAP_* can
    # create or promote the first admin user, but the login flow never uses
    # env-var credentials directly.
    # ----------------------------------------------------------------
    admin_storage_secret: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        validation_alias="ADMIN_STORAGE_SECRET",
    )
    admin_bootstrap_enabled: bool = Field(
        default=False,
        validation_alias="ADMIN_BOOTSTRAP_ENABLED",
    )
    admin_bootstrap_username: str = Field(
        default="admin",
        validation_alias="ADMIN_BOOTSTRAP_USERNAME",
        min_length=1,
        max_length=20,
    )
    admin_bootstrap_password: str | None = Field(
        default=None,
        validation_alias="ADMIN_BOOTSTRAP_PASSWORD",
        max_length=255,
    )
    admin_bootstrap_email: str = Field(
        default="admin@example.com",
        validation_alias="ADMIN_BOOTSTRAP_EMAIL",
        min_length=1,
        max_length=255,
    )
    admin_bootstrap_full_name: str = Field(
        default="Administrator",
        validation_alias="ADMIN_BOOTSTRAP_FULL_NAME",
        min_length=1,
        max_length=255,
    )

    # ----------------------------------------------------------------
    # Authentication (JWT)
    #
    # Local and quickstart use an auto-generated secret for zero-config
    # boot. Strict environments must provide JWT_SECRET_KEY explicitly.
    # ----------------------------------------------------------------
    jwt_secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_access_token_minutes: int = Field(
        default=15, validation_alias="JWT_ACCESS_TOKEN_MINUTES", ge=1
    )
    jwt_refresh_token_days: int = Field(
        default=14, validation_alias="JWT_REFRESH_TOKEN_DAYS", ge=1
    )
    jwt_issuer: str = Field(
        default="fastapi-agent-blueprint", validation_alias="JWT_ISSUER"
    )
    jwt_audience: str = Field(
        default="fastapi-agent-blueprint-api", validation_alias="JWT_AUDIENCE"
    )
    jwt_leeway_seconds: int = Field(
        default=30, validation_alias="JWT_LEEWAY_SECONDS", ge=0
    )

    # ----------------------------------------------------------------
    # Database
    #
    # Defaults target the zero-config SQLite path used by `make quickstart`.
    # For non-sqlite engines, the user/password/host/port/name fields must
    # all be supplied via env vars. stg/prod additionally reject the
    # unsafe-password and unsafe-host defaults via `_UNSAFE_DEFAULTS`.
    # ----------------------------------------------------------------
    database_engine: str = Field(default="sqlite", validation_alias="DATABASE_ENGINE")
    database_user: str = Field(default="postgres", validation_alias="DATABASE_USER")
    database_password: str = Field(
        default="postgres", validation_alias="DATABASE_PASSWORD"
    )
    database_host: str = Field(default="localhost", validation_alias="DATABASE_HOST")
    database_port: int = Field(default=5432, validation_alias="DATABASE_PORT")
    database_name: str = Field(
        default="./quickstart.db", validation_alias="DATABASE_NAME"
    )
    database_pool_size: int | None = Field(
        default=None, validation_alias="DATABASE_POOL_SIZE"
    )
    database_max_overflow: int | None = Field(
        default=None, validation_alias="DATABASE_MAX_OVERFLOW"
    )
    database_pool_recycle: int | None = Field(
        default=None, validation_alias="DATABASE_POOL_RECYCLE"
    )
    database_echo: bool | None = Field(default=None, validation_alias="DATABASE_ECHO")

    # ----------------------------------------------------------------
    # Storage (AWS S3)
    # ----------------------------------------------------------------
    s3_access_key: str | None = Field(default=None, validation_alias="S3_ACCESS_KEY")
    s3_secret_key: str | None = Field(default=None, validation_alias="S3_SECRET_KEY")
    s3_region: str | None = Field(default=None, validation_alias="S3_REGION")
    s3_bucket_name: str | None = Field(default=None, validation_alias="S3_BUCKET_NAME")

    # ----------------------------------------------------------------
    # Storage (MinIO)
    # ----------------------------------------------------------------
    minio_host: str | None = Field(default=None, validation_alias="MINIO_HOST")
    minio_port: int | None = Field(default=None, validation_alias="MINIO_PORT")
    minio_access_key: str | None = Field(
        default=None, validation_alias="MINIO_ACCESS_KEY"
    )
    minio_secret_key: str | None = Field(
        default=None, validation_alias="MINIO_SECRET_KEY"
    )
    minio_bucket_name: str | None = Field(
        default=None, validation_alias="MINIO_BUCKET_NAME"
    )

    # ----------------------------------------------------------------
    # Storage Type Selector (s3 / minio)
    # ----------------------------------------------------------------
    storage_type: str | None = Field(default=None, validation_alias="STORAGE_TYPE")

    # ----------------------------------------------------------------
    # DynamoDB (Optional)
    # ----------------------------------------------------------------
    dynamodb_region: str | None = Field(
        default=None, validation_alias="DYNAMODB_REGION"
    )
    dynamodb_access_key: str | None = Field(
        default=None, validation_alias="DYNAMODB_ACCESS_KEY"
    )
    dynamodb_secret_key: str | None = Field(
        default=None, validation_alias="DYNAMODB_SECRET_KEY"
    )
    dynamodb_endpoint_url: str | None = Field(
        default=None, validation_alias="DYNAMODB_ENDPOINT_URL"
    )

    # ----------------------------------------------------------------
    # S3 Vectors (Optional)
    # ----------------------------------------------------------------
    s3vectors_region: str | None = Field(
        default=None, validation_alias="S3VECTORS_REGION"
    )
    s3vectors_access_key: str | None = Field(
        default=None, validation_alias="S3VECTORS_ACCESS_KEY"
    )
    s3vectors_secret_key: str | None = Field(
        default=None, validation_alias="S3VECTORS_SECRET_KEY"
    )
    s3vectors_bucket_name: str | None = Field(
        default=None, validation_alias="S3VECTORS_BUCKET_NAME"
    )

    # ----------------------------------------------------------------
    # Vector Store backend selector
    # Values: ``inmemory`` (default, process-local) | ``s3vectors``.
    # Domain containers use this to pick between InMemory and S3 backends.
    # ----------------------------------------------------------------
    vector_store_type: str | None = Field(
        default=None, validation_alias="VECTOR_STORE_TYPE"
    )

    # ----------------------------------------------------------------
    # Message Broker
    # ----------------------------------------------------------------
    broker_type: str | None = Field(default=None, validation_alias="BROKER_TYPE")

    # ----------------------------------------------------------------
    # Messaging (AWS SQS) — required when BROKER_TYPE=sqs
    # ----------------------------------------------------------------
    aws_sqs_region: str | None = Field(default=None, validation_alias="AWS_SQS_REGION")
    aws_sqs_access_key: str | None = Field(
        default=None, validation_alias="AWS_SQS_ACCESS_KEY"
    )
    aws_sqs_secret_key: str | None = Field(
        default=None, validation_alias="AWS_SQS_SECRET_KEY"
    )
    aws_sqs_url: str | None = Field(default=None, validation_alias="AWS_SQS_URL")

    # ----------------------------------------------------------------
    # Messaging (RabbitMQ) — required when BROKER_TYPE=rabbitmq
    # ----------------------------------------------------------------
    rabbitmq_url: str | None = Field(default=None, validation_alias="RABBITMQ_URL")

    # ----------------------------------------------------------------
    # Embedding (Optional)
    # ----------------------------------------------------------------
    embedding_provider: str | None = Field(
        default=None, validation_alias="EMBEDDING_PROVIDER"
    )
    embedding_model: str | None = Field(
        default=None, validation_alias="EMBEDDING_MODEL"
    )

    # OpenAI-specific (required when EMBEDDING_PROVIDER=openai)
    embedding_openai_api_key: str | None = Field(
        default=None, validation_alias="EMBEDDING_OPENAI_API_KEY"
    )

    # Bedrock-specific (required when EMBEDDING_PROVIDER=bedrock)
    embedding_bedrock_access_key: str | None = Field(
        default=None, validation_alias="EMBEDDING_BEDROCK_ACCESS_KEY"
    )
    embedding_bedrock_secret_key: str | None = Field(
        default=None, validation_alias="EMBEDDING_BEDROCK_SECRET_KEY"
    )
    embedding_bedrock_region: str | None = Field(
        default=None, validation_alias="EMBEDDING_BEDROCK_REGION"
    )

    # ----------------------------------------------------------------
    # LLM (Optional — required when using PydanticAI agents)
    # ----------------------------------------------------------------
    llm_provider: str | None = Field(default=None, validation_alias="LLM_PROVIDER")
    llm_model: str | None = Field(default=None, validation_alias="LLM_MODEL")
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")

    # Bedrock-specific (required when LLM_PROVIDER=bedrock)
    llm_bedrock_access_key: str | None = Field(
        default=None, validation_alias="LLM_BEDROCK_ACCESS_KEY"
    )
    llm_bedrock_secret_key: str | None = Field(
        default=None, validation_alias="LLM_BEDROCK_SECRET_KEY"
    )
    llm_bedrock_region: str | None = Field(
        default=None, validation_alias="LLM_BEDROCK_REGION"
    )

    # ----------------------------------------------------------------
    # Observability (OpenTelemetry — Optional)
    # ----------------------------------------------------------------
    otel_enabled: bool = Field(
        default=False,
        validation_alias="OTEL_ENABLED",
        description=(
            "When True, configure_otel() runs at server/worker bootstrap, "
            "installs a global TracerProvider with OTLP gRPC exporter, and "
            "calls Agent.instrument_all() so PydanticAI Agents emit GenAI "
            "semantic-convention spans. Default False — quickstart works "
            "unchanged. Requires the [otel] extra: uv sync --extra otel."
        ),
    )
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
        description=(
            "OTLP collector endpoint. Defaults to gRPC (e.g. "
            "http://localhost:4317). Required when OTEL_ENABLED=true. "
            "See docs/operations/observability-otel.md for HTTP exporter swap."
        ),
    )

    # ----------------------------------------------------------------
    # AI Usage public API (Optional)
    # ----------------------------------------------------------------
    ai_usage_public_api_enabled: bool = Field(
        default=False,
        validation_alias="AI_USAGE_PUBLIC_API_ENABLED",
        description=(
            "Enable unauthenticated /v1/usage read endpoints. Default False; "
            "NiceGUI admin remains the safe default read surface until the "
            "project has tenant-aware API authentication."
        ),
    )

    # ----------------------------------------------------------------
    # Network Policy
    # ----------------------------------------------------------------
    allowed_hosts: list[str] = Field(
        default=["localhost", "127.0.0.1"],
        validation_alias="ALLOWED_HOSTS",
    )
    allow_origins: list[str] = Field(
        default=["*"],
        validation_alias="ALLOW_ORIGINS",
    )

    # ----------------------------------------------------------------
    # Logging (structlog)
    # ----------------------------------------------------------------
    log_level: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
        description=(
            "Root log level (DEBUG, INFO, WARNING, ERROR). Applied to both "
            "structlog-originated records and stdlib loggers routed through "
            "the ProcessorFormatter bridge."
        ),
    )
    log_json_format: bool | None = Field(
        default=None,
        validation_alias="LOG_JSON_FORMAT",
        description=(
            "Force JSON renderer on (True) or off (False). When unset, derives "
            "from ENV — dev/local/quickstart → console renderer, stg/prod → JSON. "
            "Keep this independently overridable so ops can flip console on in "
            "prod when debugging without redeploying."
        ),
    )

    # ----------------------------------------------------------------

    @model_validator(mode="after")
    def _validate_environment_safety(self) -> Self:
        errors: list[str] = []
        env = self.env.lower()

        if env not in KNOWN_ENVS:
            errors.append(
                f"[env] Unknown environment '{self.env}'. "
                f"Expected one of: {', '.join(KNOWN_ENVS)}"
            )

        engine = self.database_engine.lower()
        if engine not in KNOWN_ENGINES:
            errors.append(
                f"[database_engine] Unknown engine '{self.database_engine}'. "
                f"Expected one of: {', '.join(KNOWN_ENGINES)}"
            )

        if env in STRICT_ENVS:
            for field_name, unsafe_value in _UNSAFE_DEFAULTS.items():
                if getattr(self, field_name) == unsafe_value:
                    errors.append(
                        f"[{field_name}] Using unsafe default "
                        f"'{unsafe_value}' in '{self.env}' environment"
                    )

            if "admin_storage_secret" not in self.model_fields_set:
                errors.append(
                    f"[admin_storage_secret] ADMIN_STORAGE_SECRET must be explicitly set "
                    f"in '{self.env}' environment (auto-generated value not allowed)"
                )

            if "jwt_secret_key" not in self.model_fields_set:
                errors.append(
                    f"[jwt_secret_key] JWT_SECRET_KEY must be explicitly set "
                    f"in '{self.env}' environment (auto-generated value not allowed)"
                )

            if (
                self.admin_bootstrap_enabled
                and self.admin_bootstrap_password == "admin"  # noqa: S105
            ):
                errors.append(
                    "[admin_bootstrap_password] ADMIN_BOOTSTRAP_PASSWORD uses an "
                    "unsafe default in strict environments"
                )

            if self.dynamodb_endpoint_url:
                _local_patterns = ("localhost", "127.", "0.0.0.0", "::1")  # noqa: S104
                if any(p in self.dynamodb_endpoint_url for p in _local_patterns):
                    errors.append(
                        f"[dynamodb_endpoint_url] DYNAMODB_ENDPOINT_URL references a local "
                        f"address in '{self.env}' environment. Use an AWS endpoint URL."
                    )

            for field_name, default_value in _WARN_DEFAULTS.items():
                if getattr(self, field_name) == default_value:
                    warnings.warn(
                        f"Settings: [{field_name}] still uses default "
                        f"'{default_value}' in '{self.env}' environment",
                        stacklevel=2,
                    )

        if self.jwt_algorithm != "HS256":
            errors.append(
                f"[jwt_algorithm] Unsupported JWT algorithm '{self.jwt_algorithm}'. "
                "Only HS256 is supported in v1."
            )
        if len(self.jwt_secret_key.encode()) < 32:
            errors.append("[jwt_secret_key] JWT_SECRET_KEY must be at least 32 bytes")
        if self.jwt_secret_key in _UNSAFE_JWT_SECRETS:
            errors.append("[jwt_secret_key] JWT_SECRET_KEY uses an unsafe placeholder")
        if self.admin_bootstrap_enabled and not self.admin_bootstrap_password:
            errors.append(
                "[admin_bootstrap_password] ADMIN_BOOTSTRAP_PASSWORD must be set "
                "when ADMIN_BOOTSTRAP_ENABLED=true"
            )

        s3_fields = {
            "s3_access_key": self.s3_access_key,
            "s3_secret_key": self.s3_secret_key,
            "s3_region": self.s3_region,
            "s3_bucket_name": self.s3_bucket_name,
        }
        s3_set = {k for k, v in s3_fields.items() if v is not None}
        if s3_set and s3_set != set(s3_fields):
            missing = sorted(set(s3_fields) - s3_set)
            errors.append(
                f"[S3] Partial configuration: {', '.join(sorted(s3_set))} "
                f"set but {', '.join(missing)} missing"
            )

        minio_fields = {
            "minio_host": self.minio_host,
            "minio_port": self.minio_port,
            "minio_access_key": self.minio_access_key,
            "minio_secret_key": self.minio_secret_key,
            "minio_bucket_name": self.minio_bucket_name,
        }
        minio_set = {k for k, v in minio_fields.items() if v is not None}
        if minio_set and minio_set != set(minio_fields):
            missing = sorted(set(minio_fields) - minio_set)
            errors.append(
                f"[MinIO] Partial configuration: {', '.join(sorted(minio_set))} "
                f"set but {', '.join(missing)} missing"
            )

        storage = (self.storage_type or "").lower().strip()
        if storage and storage not in KNOWN_STORAGE_TYPES:
            errors.append(
                f"[storage_type] Unknown storage type '{self.storage_type}'. "
                f"Expected one of: {', '.join(KNOWN_STORAGE_TYPES)}"
            )
        if storage == "s3" and s3_set != set(s3_fields):
            missing = sorted(set(s3_fields) - s3_set)
            errors.append(
                f"[Storage] STORAGE_TYPE=s3 requires: {', '.join(missing)} missing"
            )
        if storage == "minio" and minio_set != set(minio_fields):
            missing = sorted(set(minio_fields) - minio_set)
            errors.append(
                f"[Storage] STORAGE_TYPE=minio requires: {', '.join(missing)} missing"
            )

        dynamodb_fields = {
            "dynamodb_region": self.dynamodb_region,
            "dynamodb_access_key": self.dynamodb_access_key,
            "dynamodb_secret_key": self.dynamodb_secret_key,
        }
        dynamodb_set = {k for k, v in dynamodb_fields.items() if v is not None}
        if dynamodb_set and dynamodb_set != set(dynamodb_fields):
            missing = sorted(set(dynamodb_fields) - dynamodb_set)
            errors.append(
                f"[DynamoDB] Partial configuration: "
                f"{', '.join(sorted(dynamodb_set))} "
                f"set but {', '.join(missing)} missing"
            )

        s3vectors_fields = {
            "s3vectors_region": self.s3vectors_region,
            "s3vectors_access_key": self.s3vectors_access_key,
            "s3vectors_secret_key": self.s3vectors_secret_key,
            "s3vectors_bucket_name": self.s3vectors_bucket_name,
        }
        s3vectors_set = {k for k, v in s3vectors_fields.items() if v is not None}
        if s3vectors_set and s3vectors_set != set(s3vectors_fields):
            missing = sorted(set(s3vectors_fields) - s3vectors_set)
            errors.append(
                f"[S3Vectors] Partial configuration: "
                f"{', '.join(sorted(s3vectors_set))} "
                f"set but {', '.join(missing)} missing"
            )

        broker = (self.broker_type or "").lower().strip()
        if env in STRICT_ENVS and not broker:
            errors.append(
                f"[broker_type] BROKER_TYPE is required in '{self.env}' environment"
            )
        if broker and broker not in KNOWN_BROKER_TYPES:
            errors.append(
                f"[broker_type] Unknown broker type '{self.broker_type}'. "
                f"Expected one of: {', '.join(KNOWN_BROKER_TYPES)}"
            )

        if broker == "sqs":
            sqs_fields = {
                "aws_sqs_access_key": self.aws_sqs_access_key,
                "aws_sqs_secret_key": self.aws_sqs_secret_key,
                "aws_sqs_url": self.aws_sqs_url,
            }
            sqs_set = {k for k, v in sqs_fields.items() if v is not None}
            if sqs_set != set(sqs_fields):
                missing = sorted(set(sqs_fields) - sqs_set)
                errors.append(
                    f"[SQS] BROKER_TYPE=sqs requires: {', '.join(missing)} missing"
                )

        if broker == "rabbitmq" and not self.rabbitmq_url:
            errors.append(
                "[RabbitMQ] BROKER_TYPE=rabbitmq requires: rabbitmq_url missing"
            )

        llm = (self.llm_provider or "").lower().strip()
        if llm and llm not in KNOWN_LLM_PROVIDERS:
            errors.append(
                f"[llm_provider] Unknown LLM provider '{self.llm_provider}'. "
                f"Expected one of: {', '.join(KNOWN_LLM_PROVIDERS)}"
            )

        if llm in ("openai", "anthropic") and not self.llm_api_key:
            errors.append(f"[LLM] LLM_PROVIDER={llm} requires: llm_api_key missing")

        if llm == "bedrock":
            llm_bedrock_fields = {
                "llm_bedrock_access_key": self.llm_bedrock_access_key,
                "llm_bedrock_secret_key": self.llm_bedrock_secret_key,
                "llm_bedrock_region": self.llm_bedrock_region,
            }
            llm_bedrock_set = {
                k for k, v in llm_bedrock_fields.items() if v is not None
            }
            if llm_bedrock_set != set(llm_bedrock_fields):
                missing = sorted(set(llm_bedrock_fields) - llm_bedrock_set)
                errors.append(
                    f"[LLM/Bedrock] LLM_PROVIDER=bedrock requires: "
                    f"{', '.join(missing)} missing"
                )

        embedding = (self.embedding_provider or "").lower().strip()
        if embedding and embedding not in KNOWN_EMBEDDING_PROVIDERS:
            errors.append(
                f"[embedding_provider] Unknown embedding provider "
                f"'{self.embedding_provider}'. "
                f"Expected one of: {', '.join(KNOWN_EMBEDDING_PROVIDERS)}"
            )

        if embedding == "openai":
            if not self.embedding_openai_api_key:
                errors.append(
                    "[Embedding/OpenAI] EMBEDDING_PROVIDER=openai requires: "
                    "embedding_openai_api_key missing"
                )

        if embedding == "bedrock":
            bedrock_fields = {
                "embedding_bedrock_access_key": self.embedding_bedrock_access_key,
                "embedding_bedrock_secret_key": self.embedding_bedrock_secret_key,
                "embedding_bedrock_region": self.embedding_bedrock_region,
            }
            bedrock_set = {k for k, v in bedrock_fields.items() if v is not None}
            if bedrock_set != set(bedrock_fields):
                missing = sorted(set(bedrock_fields) - bedrock_set)
                errors.append(
                    f"[Embedding/Bedrock] EMBEDDING_PROVIDER=bedrock requires: "
                    f"{', '.join(missing)} missing"
                )

        if self.otel_enabled and not self.otel_exporter_otlp_endpoint:
            errors.append(
                "[OTEL] OTEL_ENABLED=true requires: otel_exporter_otlp_endpoint missing"
            )

        if env in STRICT_ENVS and self.ai_usage_public_api_enabled:
            errors.append(
                "[AI Usage] AI_USAGE_PUBLIC_API_ENABLED=true is forbidden in "
                f"'{self.env}' until tenant-aware API authentication exists"
            )

        if errors:
            bullet_list = "\n  - ".join(errors)
            raise ValueError(
                f"Settings validation failed for env='{self.env}' "
                f"({len(errors)} error(s)):\n  - {bullet_list}"
            )

        return self

    @property
    def is_dev(self) -> bool:
        return self.env.lower() in {"quickstart", "dev", "local"}

    @property
    def effective_log_json(self) -> bool:
        """Whether the JSON renderer is active for this process.

        Respects an explicit ``LOG_JSON_FORMAT`` override when set; otherwise
        defaults to console for dev envs and JSON for non-dev (stg/prod + any
        unrecognised env). Keep the explicit override path so ops can flip
        console on in prod without redeploying Settings.
        """
        if self.log_json_format is not None:
            return self.log_json_format
        return not self.is_dev

    @property
    def docs_url(self) -> str | None:
        return "/docs-swagger" if self.is_dev else None

    @property
    def redoc_url(self) -> str | None:
        return "/docs-redoc" if self.is_dev else None

    @property
    def openapi_url(self) -> str | None:
        return "/openapi.json" if self.is_dev else None

    @property
    def minio_endpoint_url(self) -> str | None:
        if self.minio_host and self.minio_port:
            return f"{self.minio_host}:{self.minio_port}"
        return None

    @property
    def storage_access_key(self) -> str | None:
        st = (self.storage_type or "").lower()
        if st == "s3":
            return self.s3_access_key
        if st == "minio":
            return self.minio_access_key
        return None

    @property
    def storage_secret_key(self) -> str | None:
        st = (self.storage_type or "").lower()
        if st == "s3":
            return self.s3_secret_key
        if st == "minio":
            return self.minio_secret_key
        return None

    @property
    def storage_region(self) -> str | None:
        st = (self.storage_type or "").lower()
        if st == "s3":
            return self.s3_region
        if st == "minio":
            return "us-east-1"
        return None

    @property
    def storage_endpoint_url(self) -> str | None:
        st = (self.storage_type or "").lower()
        if st == "minio":
            return self.minio_endpoint_url
        return None

    @property
    def storage_bucket_name(self) -> str | None:
        st = (self.storage_type or "").lower()
        if st == "s3":
            return self.s3_bucket_name
        if st == "minio":
            return self.minio_bucket_name
        return None

    @property
    def embedding_dimension(self) -> int:
        """Derive embedding vector dimension from provider and model.

        Not user-configurable — determined by the selected model.
        Used as the single source of truth for ``VectorModelMeta.dimension``.
        """
        provider = (self.embedding_provider or "openai").lower()
        model = self.embedding_model
        if provider == "bedrock":
            return _BEDROCK_DIMENSIONS.get(
                model or "amazon.titan-embed-text-v2:0", 1024
            )
        if provider == "google":
            return _GOOGLE_DIMENSIONS.get(model or "gemini-embedding-001", 768)
        if provider in ("ollama", "sentence-transformers"):
            return _LOCAL_DIMENSIONS.get(model or "nomic-embed-text", 768)
        return _OPENAI_DIMENSIONS.get(model or "text-embedding-3-small", 1536)

    @property
    def embedding_model_name(self) -> str | None:
        """PydanticAI-compatible embedding model string.

        e.g. ``'openai:text-embedding-3-small'``, ``'bedrock:amazon.titan-embed-text-v2:0'``.
        Returns ``None`` when embedding is not configured.
        """
        provider = (self.embedding_provider or "").lower().strip()
        model = self.embedding_model
        if not provider or not model:
            return None
        return f"{provider}:{model}"

    @property
    def llm_model_name(self) -> str | None:
        """PydanticAI-compatible model string (e.g. ``'openai:gpt-4o'``).

        Returns ``None`` when LLM is not configured.
        """
        provider = (self.llm_provider or "").lower().strip()
        model = self.llm_model
        if not provider or not model:
            return None
        return f"{provider}:{model}"


settings = Settings()
