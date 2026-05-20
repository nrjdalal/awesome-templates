from __future__ import annotations

from src._core.domain.value_objects.llm_config import LLMConfig
from src._core.infrastructure.ai.providers import (
    build_anthropic_provider,
    build_bedrock_provider,
    build_openai_provider,
    parse_model_name,
)


def build_llm_model(llm_config: LLMConfig):  # noqa: ANN201
    """Build a PydanticAI Model object or return a model string.

    - Explicit credentials → construct Provider for precise auth control.
    - No credentials → return plain model string (PydanticAI env var fallback).
    """
    provider, raw_model = parse_model_name(llm_config.model_name)

    if provider == "bedrock" and llm_config.aws_access_key_id:
        from pydantic_ai.models.bedrock import BedrockConverseModel

        return BedrockConverseModel(
            raw_model,
            provider=build_bedrock_provider(
                llm_config.aws_access_key_id,
                llm_config.aws_secret_access_key,
                llm_config.aws_region,
            ),
        )

    if provider == "openai" and llm_config.api_key:
        from pydantic_ai.models.openai import OpenAIChatModel

        return OpenAIChatModel(
            raw_model,
            provider=build_openai_provider(llm_config.api_key),
        )

    if provider == "anthropic" and llm_config.api_key:
        from pydantic_ai.models.anthropic import AnthropicModel

        return AnthropicModel(
            raw_model,
            provider=build_anthropic_provider(llm_config.api_key),
        )

    return llm_config.model_name
