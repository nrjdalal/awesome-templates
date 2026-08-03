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


def _notification_selector() -> str:
    return "enabled" if settings.notification_webhook_url else "disabled"


def _notification_tier_selector(override_url: str | None, target: str | None) -> str:
    """Three-way branch for a per-tier notification client (#327).

    ``"shared"`` is the branch that matters. Both tier targets fall back to the
    single provider webhook, so a two-way enabled/disabled selector built a
    *separate adapter against the same URL* for every tier: with routing on and no
    overrides, three ``SlackNotificationAdapter`` instances for one channel.
    Probed at HEAD before this change — ``distinct adapter objects: 3``.

    That footprint is not cosmetic. Both defects found in round 1 of PR #313 were
    consequences of it: three ``NoopNotificationClient`` instances instead of one
    (so the disabled warning logged three times), and an injected client the router
    short-circuits. The symptoms were patched then; this removes the shape.

    An adapter is only built for a tier that has its own URL. Otherwise the tier
    resolves to ``notification_client`` — the same object, not a copy — so the
    delivered URL is unchanged and only the instance count drops.
    """
    if not target:
        return "disabled"
    return "override" if override_url else "shared"


def _notification_critical_selector() -> str:
    return _notification_tier_selector(
        settings.notification_critical_webhook_url,
        settings.notification_critical_target,
    )


def _notification_warning_selector() -> str:
    return _notification_tier_selector(
        settings.notification_warning_webhook_url,
        settings.notification_warning_target,
    )


def _notification_routing_selector() -> str:
    """#286 severity routing is opt-in, and NOTIFICATION_WARNING_THRESHOLD is
    the only switch: a per-tier webhook URL does not enable routing on its own
    (that combination is rejected at boot — see the [Notification/Routing]
    checks in ``config.py``, #315).

    With the threshold unset, ``notification_router`` resolves to ``None`` and
    ``ErrorNotifier`` takes its ``else self._client`` branch — the #17
    single-target path, gated at NOTIFICATION_SEVERITY_THRESHOLD with the
    cooldown keyed on the bare ``error_code``. That path stays live in
    production, not only in tests that construct ``ErrorNotifier`` directly."""
    return (
        "enabled" if settings.notification_warning_threshold is not None else "disabled"
    )


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


def _build_notification_client(
    http_client: HttpClient, provider: str | None, webhook_url: str | None
):
    from src._core.infrastructure.notification.discord_notification_adapter import (
        DiscordNotificationAdapter,
    )
    from src._core.infrastructure.notification.slack_notification_adapter import (
        SlackNotificationAdapter,
    )

    if (provider or "").lower().strip() == "discord":
        return DiscordNotificationAdapter(
            http_client=http_client, webhook_url=webhook_url or ""
        )
    return SlackNotificationAdapter(
        http_client=http_client, webhook_url=webhook_url or ""
    )


def _build_noop_notification_client():
    from src._core.infrastructure.notification.noop_notification_client import (
        NoopNotificationClient,
    )

    return NoopNotificationClient()


def _build_notification_router(
    critical_client,
    warning_client,
    severity_threshold: int,
    warning_threshold: int | None,
):
    from src._core.infrastructure.notification.notification_router import (
        NotificationRouter,
    )

    return NotificationRouter(
        critical_client=critical_client,
        warning_client=warning_client,
        severity_threshold=severity_threshold,
        warning_threshold=warning_threshold,
    )


def _build_error_notifier(
    notification_client,
    severity_threshold: int,
    cooldown_seconds: int,
    notification_router=None,
):
    from src._core.infrastructure.notification.error_notifier import ErrorNotifier

    return ErrorNotifier(
        notification_client=notification_client,
        severity_threshold=severity_threshold,
        cooldown_seconds=cooldown_seconds,
        notification_router=notification_router,
    )


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

    #########################################################
    # Error Notification (optional — NOTIFICATION_PROVIDER=slack|discord)
    # Disabled → NoopNotificationClient so ErrorNotifier always has a
    # client to call, regardless of whether Slack/Discord is configured.
    #########################################################

    # Shared across all three notification Selectors below: NoopNotification
    # Client logs its "disabled" warning from __init__, so a separate
    # Singleton per Selector means a separate log line per Selector too.
    # One shared instance -> one warning, regardless of how many tiers are
    # wired (#313 review).
    _noop_notification_client = providers.Singleton(_build_noop_notification_client)

    notification_client = providers.Selector(
        _notification_selector,
        enabled=providers.Singleton(
            _build_notification_client,
            http_client=http_client,
            provider=settings.notification_provider,
            webhook_url=settings.notification_webhook_url,
        ),
        disabled=_noop_notification_client,
    )

    #########################################################
    # Severity-based channel routing (optional — #286, on top of #17).
    # Each tier resolves its own target, falling back to the single
    # notification_client webhook above when no override is set.
    # These two providers are consumed only by notification_router below,
    # which is itself gated on NOTIFICATION_WARNING_THRESHOLD — so with
    # routing off they are declared but never resolved.
    #########################################################

    notification_critical_client = providers.Selector(
        _notification_critical_selector,
        override=providers.Singleton(
            _build_notification_client,
            http_client=http_client,
            provider=settings.notification_provider,
            webhook_url=settings.notification_critical_webhook_url,
        ),
        # No override: reuse the base client object rather than building a second
        # adapter against the same URL. See _notification_tier_selector.
        shared=notification_client,
        disabled=_noop_notification_client,
    )

    notification_warning_client = providers.Selector(
        _notification_warning_selector,
        override=providers.Singleton(
            _build_notification_client,
            http_client=http_client,
            provider=settings.notification_provider,
            webhook_url=settings.notification_warning_webhook_url,
        ),
        shared=notification_client,
        disabled=_noop_notification_client,
    )

    # Only wired when NOTIFICATION_WARNING_THRESHOLD is set — otherwise
    # notification_router stays None and error_notifier's
    # `notification_client` (the single-target base client, unchanged from
    # #17) is the one actually sent through. See
    # _notification_routing_selector for why the per-tier URLs cannot enable
    # routing by themselves.
    notification_router = providers.Selector(
        _notification_routing_selector,
        enabled=providers.Singleton(
            _build_notification_router,
            critical_client=notification_critical_client,
            warning_client=notification_warning_client,
            severity_threshold=settings.notification_severity_threshold,
            warning_threshold=settings.notification_warning_threshold,
        ),
        disabled=providers.Object(None),
    )

    error_notifier = providers.Singleton(
        _build_error_notifier,
        notification_client=notification_client,
        severity_threshold=settings.notification_severity_threshold,
        cooldown_seconds=settings.notification_cooldown_seconds,
        notification_router=notification_router,
    )
