from __future__ import annotations

from typing import Protocol, runtime_checkable

from src._core.domain.value_objects.prompt_snapshot import PromptSnapshot


@runtime_checkable
class PromptProviderProtocol(Protocol):
    """Resolves the active version of a named prompt at execution time.

    This is the ``get_active(name) -> PromptSnapshot`` contract ADR 046 §4
    reserved; ADR 066 implements it. The caller always passes ``default`` —
    the prompt text shipped in code — so a provider never needs a registry
    of its own and an unreachable backend degrades to the code value instead
    of failing the request.

    Implementations must not raise for a backend failure: they return a
    snapshot built from ``default`` with ``source="inline"``.

    Bundled implementations (``src/_core/infrastructure/prompt/``):
    - ``InlinePromptProvider`` — returns ``default`` (quickstart / unset).
    An operator-editable, DB-backed provider (``source="self"``) is the planned
    second implementation; it must keep the same degrade-to-``default`` rule.
    """

    async def get_active(self, name: str, *, default: str) -> PromptSnapshot: ...
