"""Stub LLM model used when ``LLM_PROVIDER`` + ``LLM_MODEL`` are unset.

Wraps PydanticAI's ``TestModel`` so any domain that builds an
``Agent(model=llm_model, output_type=...)`` still round-trips in
``make quickstart`` without real LLM credentials. The canned response
shape follows whatever ``output_type`` the consumer declares — it is
not meaningful content, just a valid structured payload.

When the ``pydantic-ai`` optional extra is not installed the factory
returns ``None`` instead of raising: an LLM consumer domain that has
not installed its runtime cannot use the stub anyway, and letting
``CoreContainer.llm_model()`` boot to ``None`` is exactly the
acceptance criterion #101 locked in (Part A). The ``None`` propagates
harmlessly unless a domain actually touches it, at which point
``ClassificationService``-style import guards surface the "install
pydantic-ai" hint.

Matches the ``StubEmbedder`` / ``StubAnswerAgent`` contract: logs a
warning at construction so quickstart users notice that responses are
templated, not generated.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_stub_llm_model() -> Any | None:
    """Build a PydanticAI-compatible stub model, or ``None`` if the
    ``pydantic-ai`` extra is not installed.

    Lazy-imports ``pydantic_ai`` so removing the optional extra does
    not break module import. Returning ``None`` on missing pydantic-ai
    keeps the #101 Part A boot guarantee intact: the app still starts,
    just without an LLM stub available. Domains that actually use the
    stub are already gated by their own ``pydantic-ai`` import (e.g.
    ``ClassificationService.__init__``).
    """
    try:
        from pydantic_ai.models.test import TestModel
    except ImportError:
        logger.info(
            "LLM stub not instantiated — pydantic-ai is not installed. "
            "Install with: uv sync --extra pydantic-ai "
            "to enable the Agent-compatible stub fallback."
        )
        return None

    logger.warning(
        "LLM stub model active — responses are templated, not generated. "
        "Set LLM_PROVIDER + LLM_MODEL for real answers."
    )
    return TestModel()
