from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingConfig:
    """Immutable embedding configuration for domain services.

    Domain services use this to construct PydanticAI Embedders.
    Follows the LLMConfig pattern (ADR 037) — domain-layer value object.

    ``model_name`` is a PydanticAI-compatible string,
    e.g. ``"openai:text-embedding-3-small"``.

    Bedrock credentials follow the project convention of per-service
    credential injection (same as DynamoDB, SQS, S3Vectors).
    When ``aws_*`` fields are ``None``, PydanticAI falls back to
    the boto3 credentials chain (``AWS_ACCESS_KEY_ID`` env var etc.).
    """

    model_name: str
    dimension: int = 1536
    api_key: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str | None = None
