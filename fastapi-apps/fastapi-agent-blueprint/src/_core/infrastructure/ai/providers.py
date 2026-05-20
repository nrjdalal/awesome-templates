"""Shared PydanticAI provider construction helpers.

Single source of truth for the ``"provider:raw_model"`` name convention
and explicit-credential provider wiring shared by the LLM model factory
and the embedding adapter.

All provider imports are lazy so the ``pydantic-ai`` extra is not required
at module import time — consistent with ADR 042 lazy-import policy.
"""

from __future__ import annotations


def parse_model_name(name: str) -> tuple[str, str]:
    """Split ``"provider:raw_model"`` into ``(provider, raw_model)``.

    Returns ``("", name)`` when no colon prefix is present so callers
    can treat an empty-string provider as "let PydanticAI auto-detect".
    """
    if ":" not in name:
        return "", name
    provider, _, raw = name.partition(":")
    return provider, raw


def build_bedrock_provider(
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
    aws_region: str | None,
):  # noqa: ANN202
    """Construct a ``BedrockProvider`` from explicit credentials."""
    from pydantic_ai.providers.bedrock import BedrockProvider

    return BedrockProvider(
        region_name=aws_region or "us-east-1",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def build_openai_provider(api_key: str):  # noqa: ANN202
    """Construct an ``OpenAIProvider`` with an explicit API key."""
    from pydantic_ai.providers.openai import OpenAIProvider

    return OpenAIProvider(api_key=api_key)


def build_anthropic_provider(api_key: str):  # noqa: ANN202
    """Construct an ``AnthropicProvider`` with an explicit API key."""
    from pydantic_ai.providers.anthropic import AnthropicProvider

    return AnthropicProvider(api_key=api_key)
