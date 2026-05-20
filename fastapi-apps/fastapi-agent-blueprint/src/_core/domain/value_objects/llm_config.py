from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    """Immutable LLM configuration for domain services.

    Domain services use this to construct PydanticAI Agents.
    Follows the EmbeddingConfig pattern (domain-layer value object).

    ``model_name`` is a PydanticAI-compatible string, e.g. ``"openai:gpt-4o"``.

    Bedrock credentials follow the project convention of per-service
    credential injection (same as DynamoDB, SQS, S3Vectors, Embedding).
    When ``aws_*`` fields are ``None``, PydanticAI falls back to
    the boto3 credentials chain (``AWS_ACCESS_KEY_ID`` env var etc.).
    """

    model_name: str
    api_key: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str | None = None
