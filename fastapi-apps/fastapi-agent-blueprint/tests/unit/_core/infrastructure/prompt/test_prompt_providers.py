"""Prompt providers (#447, ADR 066).

Only the inline provider ships today. The DB-backed provider that lets
operators edit personas is a follow-up; it implements the same protocol, so
the consumer and ledger tests elsewhere do not change when it lands.
"""

from __future__ import annotations

from src._core.domain.protocols.prompt_provider_protocol import (
    PromptProviderProtocol,
)
from src._core.infrastructure.prompt.inline_prompt_provider import (
    InlinePromptProvider,
)

_DEFAULT = "You are the code persona."


def test_inline_provider_satisfies_the_protocol() -> None:
    assert isinstance(InlinePromptProvider(), PromptProviderProtocol)


async def test_inline_returns_the_code_text() -> None:
    snapshot = await InlinePromptProvider().get_active("docs_answer", default=_DEFAULT)
    assert snapshot.name == "docs_answer"
    assert snapshot.content == _DEFAULT
    assert snapshot.source == "inline"
    assert snapshot.version is None
    assert snapshot.external_ref is None
