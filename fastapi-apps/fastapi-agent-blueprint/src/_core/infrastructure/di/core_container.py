"""Core DI container.

Optional infrastructure follows the same pattern as ``broker`` (see
``src/_core/infrastructure/taskiq/broker.py`` and ADR 029 / ADR 042):

- A ``_<infra>_selector()`` module-scope function reads ``settings`` and
  returns ``"enabled"`` or ``"disabled"``.
- A ``_build_<infra>()`` factory lazy-imports the real client inside, so
  removing an optional extra (``pydantic-ai-slim``, etc.) does not break
  app boot when the infra is not configured.
- The provider is a ``providers.Selector`` whose disabled branch returns
  either ``providers.Object(None)`` (data stores — a fake client would
  mislead) or a stub instance (LLM / Embedding — domains need graceful
  degradation).

Infrastructure that is always required (RDB database, HTTP client) is
registered as a plain ``providers.Singleton`` as before.
"""

from dependency_injector import containers, providers
from taskiq import InMemoryBroker

from src._core.config import settings
from src._core.infrastructure.http.http_client import HttpClient
from src._core.infrastructure.persistence.rdb.config import DatabaseConfig
from src._core.infrastructure.persistence.rdb.database import Database
from src._core.infrastructure.taskiq.broker import (
    create_rabbitmq_broker,
    create_sqs_broker,
)
from src._core.infrastructure.taskiq.manager import TaskiqManager

# ---------------------------------------------------------------------------
# Selector functions — read ``settings`` at resolution time, so tests can
# monkeypatch settings fields to flip branches.
# ---------------------------------------------------------------------------


def _storage_selector() -> str:
    return "enabled" if settings.storage_type else "disabled"


def _dynamodb_selector() -> str:
    return "enabled" if settings.dynamodb_access_key else "disabled"


def _s3vector_selector() -> str:
    return "enabled" if settings.s3vectors_access_key else "disabled"


def _embedding_selector() -> str:
    return "enabled" if settings.embedding_model_name else "disabled"


def _llm_selector() -> str:
    return "enabled" if settings.llm_model_name else "disabled"


# ---------------------------------------------------------------------------
# Lazy factories — imports happen inside so that uninstalling the matching
# optional extra (aws, pydantic-ai, …) does not break import of this module.
# ---------------------------------------------------------------------------


def _build_storage_client(
    access_key: str | None,
    secret_access_key: str | None,
    region_name: str | None,
    endpoint_url: str | None,
):
    from src._core.infrastructure.storage.object_storage_client import (
        ObjectStorageClient,
    )

    # Selector guarantees these are populated when the enabled branch runs;
    # ``or ""`` keeps pyright happy without a runtime guard.
    return ObjectStorageClient(
        access_key=access_key or "",
        secret_access_key=secret_access_key or "",
        region_name=region_name or "ap-northeast-2",
        endpoint_url=endpoint_url,
    )


def _build_storage(storage_client, bucket_name: str | None):
    from src._core.infrastructure.storage.object_storage import ObjectStorage

    return ObjectStorage(
        storage_client=storage_client,
        bucket_name=bucket_name or "",
    )


def _build_dynamodb_client(
    access_key: str | None,
    secret_access_key: str | None,
    region_name: str | None,
    endpoint_url: str | None,
):
    from src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_client import (
        DynamoDBClient,
    )

    return DynamoDBClient(
        access_key=access_key or "",
        secret_access_key=secret_access_key or "",
        region_name=region_name or "ap-northeast-2",
        endpoint_url=endpoint_url,
    )


def _build_s3vector_client(
    access_key: str | None,
    secret_access_key: str | None,
    region_name: str | None,
):
    from src._core.infrastructure.vectors.s3.client import S3VectorClient

    return S3VectorClient(
        access_key=access_key or "",
        secret_access_key=secret_access_key or "",
        region_name=region_name or "us-east-2",
    )


def _build_embedding_client(
    model_name: str | None,
    dimension: int,
    api_key: str | None,
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
    aws_region: str | None,
):
    try:
        from src._core.domain.value_objects.embedding_config import EmbeddingConfig
        from src._core.infrastructure.embedding.pydantic_ai_embedding_adapter import (
            PydanticAIEmbeddingAdapter,
        )
    except ImportError as exc:
        raise ImportError(
            "pydantic-ai is required for the configured EMBEDDING_PROVIDER. "
            "Install it with: uv sync --extra pydantic-ai"
        ) from exc

    config = EmbeddingConfig(
        model_name=model_name or "",
        dimension=dimension,
        api_key=api_key,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_region=aws_region,
    )
    return PydanticAIEmbeddingAdapter(embedding_config=config)


def _build_stub_embedder(dimension: int):
    from src._core.infrastructure.rag.stub_embedder import StubEmbedder

    return StubEmbedder(dimension=dimension)


def _build_stub_llm_model():
    from src._core.infrastructure.llm.stub_llm_model import build_stub_llm_model

    return build_stub_llm_model()


def _build_llm_model(
    model_name: str,
    api_key: str | None,
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
    aws_region: str | None,
):
    try:
        from src._core.domain.value_objects.llm_config import LLMConfig
        from src._core.infrastructure.llm.model_factory import build_llm_model
    except ImportError as exc:
        raise ImportError(
            "pydantic-ai is required for the configured LLM_PROVIDER. "
            "Install it with: uv sync --extra pydantic-ai"
        ) from exc

    config = LLMConfig(
        model_name=model_name,
        api_key=api_key,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_region=aws_region,
    )
    return build_llm_model(llm_config=config)


class CoreContainer(containers.DeclarativeContainer):
    #########################################################
    # Database (always required)
    #########################################################

    db_config = providers.Factory(
        DatabaseConfig.from_env,
        env=settings.env,
        engine=settings.database_engine,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_recycle=settings.database_pool_recycle,
        echo=settings.database_echo,
    )

    database = providers.Singleton(
        Database,
        database_engine=settings.database_engine,
        database_user=settings.database_user,
        database_password=settings.database_password,
        database_host=settings.database_host,
        database_port=settings.database_port,
        database_name=settings.database_name,
        config=db_config,
    )

    #########################################################
    # HTTP Client (always available — pure-Python client)
    #########################################################

    http_client = providers.Singleton(
        HttpClient,
        env=settings.env,
    )

    #########################################################
    # Storage (optional — STORAGE_TYPE=s3|minio)
    #########################################################

    storage_client = providers.Selector(
        _storage_selector,
        enabled=providers.Singleton(
            _build_storage_client,
            access_key=settings.storage_access_key,
            secret_access_key=settings.storage_secret_key,
            region_name=settings.storage_region,
            endpoint_url=settings.storage_endpoint_url,
        ),
        disabled=providers.Object(None),
    )

    storage = providers.Selector(
        _storage_selector,
        enabled=providers.Factory(
            _build_storage,
            storage_client=storage_client,
            bucket_name=settings.storage_bucket_name,
        ),
        disabled=providers.Object(None),
    )

    #########################################################
    # DynamoDB (optional — DYNAMODB_* env vars)
    #########################################################

    dynamodb_client = providers.Selector(
        _dynamodb_selector,
        enabled=providers.Singleton(
            _build_dynamodb_client,
            access_key=settings.dynamodb_access_key,
            secret_access_key=settings.dynamodb_secret_key,
            region_name=settings.dynamodb_region,
            endpoint_url=settings.dynamodb_endpoint_url,
        ),
        disabled=providers.Object(None),
    )

    #########################################################
    # S3 Vectors (optional — S3VECTORS_* env vars)
    #########################################################

    s3vector_client = providers.Selector(
        _s3vector_selector,
        enabled=providers.Singleton(
            _build_s3vector_client,
            access_key=settings.s3vectors_access_key,
            secret_access_key=settings.s3vectors_secret_key,
            region_name=settings.s3vectors_region,
        ),
        disabled=providers.Object(None),
    )

    #########################################################
    # Message Queue (Taskiq) — Broker selector (SQS/RabbitMQ/InMemory)
    #########################################################

    broker = providers.Selector(
        lambda: (settings.broker_type or "inmemory").lower().strip(),
        sqs=providers.Singleton(
            create_sqs_broker,
            queue_url=settings.aws_sqs_url,
            aws_region=settings.aws_sqs_region,
            aws_access_key_id=settings.aws_sqs_access_key,
            aws_secret_access_key=settings.aws_sqs_secret_key,
        ),
        rabbitmq=providers.Singleton(
            create_rabbitmq_broker,
            url=settings.rabbitmq_url,
        ),
        inmemory=providers.Singleton(InMemoryBroker),
    )

    taskiq_manager = providers.Singleton(
        TaskiqManager,
        broker=broker,
    )

    #########################################################
    # Embedding (optional — EMBEDDING_PROVIDER + EMBEDDING_MODEL)
    # Disabled → StubEmbedder so consumer domains degrade gracefully.
    #########################################################

    embedding_client = providers.Selector(
        _embedding_selector,
        enabled=providers.Singleton(
            _build_embedding_client,
            model_name=settings.embedding_model_name,
            dimension=settings.embedding_dimension,
            api_key=settings.embedding_openai_api_key,
            aws_access_key_id=settings.embedding_bedrock_access_key,
            aws_secret_access_key=settings.embedding_bedrock_secret_key,
            aws_region=settings.embedding_bedrock_region,
        ),
        disabled=providers.Singleton(
            _build_stub_embedder,
            dimension=settings.embedding_dimension,
        ),
    )

    #########################################################
    # LLM (optional — LLM_PROVIDER + LLM_MODEL)
    # Disabled → PydanticAI TestModel via ``build_stub_llm_model`` so
    # domains like ``classification`` can degrade gracefully.
    #########################################################

    llm_model = providers.Selector(
        _llm_selector,
        enabled=providers.Singleton(
            _build_llm_model,
            model_name=settings.llm_model_name or "",
            api_key=settings.llm_api_key,
            aws_access_key_id=settings.llm_bedrock_access_key,
            aws_secret_access_key=settings.llm_bedrock_secret_key,
            aws_region=settings.llm_bedrock_region,
        ),
        disabled=providers.Singleton(_build_stub_llm_model),
    )
