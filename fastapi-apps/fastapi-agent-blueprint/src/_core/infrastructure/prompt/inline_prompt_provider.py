from __future__ import annotations

from src._core.domain.value_objects.prompt_snapshot import PromptSnapshot


def inline_snapshot(name: str, default: str) -> PromptSnapshot:
    """The snapshot for a prompt served from code.

    Public so an operator-editable provider can reuse it on its degraded path:
    the ledger must not claim an edited version for a call that ran on the
    code text.
    """
    return PromptSnapshot(name=name, content=default, source="inline")


class InlinePromptProvider:
    """Default provider: the prompt is the text shipped in code.

    The only implementation today (``CoreContainer.prompt_provider``), so
    every environment behaves exactly as before #447 — except that usage rows
    now name the prompt that served the call. The planned DB-backed provider
    (#451) replaces it in the container and falls back to it on failure.
    """

    async def get_active(self, name: str, *, default: str) -> PromptSnapshot:
        return inline_snapshot(name, default)
