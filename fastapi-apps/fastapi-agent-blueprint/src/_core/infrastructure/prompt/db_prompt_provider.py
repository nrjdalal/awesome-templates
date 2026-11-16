"""DB-backed prompt provider (#451, ADR 066).

Serves the active stored version of a prompt, or the code text when there is
none. Two deliberate choices:

- **No cache.** Every agent call reads the active version once (one indexed
  join). An LLM call takes seconds; the read is noise next to it. In exchange
  every process switches on its next call after an activation or rollback —
  the propagation window measured during #449 (a per-process TTL cache served
  different versions from different processes) does not exist here.
- **Never fails a request.** Any store error serves the code text, recorded as
  ``inline``, and logs ``prompt_store_unavailable`` (ADR066-G2).
"""

from __future__ import annotations

import structlog

from src._core.domain.value_objects.prompt_snapshot import PromptSnapshot
from src._core.infrastructure.prompt.inline_prompt_provider import inline_snapshot
from src._core.infrastructure.prompt.repository import PromptStoreRepository

_logger = structlog.stdlib.get_logger(__name__)


class DbPromptProvider:
    def __init__(self, repository: PromptStoreRepository) -> None:
        self._repository = repository

    async def get_active(self, name: str, *, default: str) -> PromptSnapshot:
        try:
            active = await self._repository.get_active(name)
            if active is None:
                return inline_snapshot(name, default)
            version = str(active.version)
            # Inside the try: a stored row the snapshot rejects (e.g. empty
            # text written around the service) is store corruption, and must
            # degrade like any other store failure rather than fail the call.
            return PromptSnapshot(
                name=name,
                content=active.content,
                version=version,
                source="self",
                # Versions are append-only, so name@version names exact text.
                external_ref=f"{name}@{version}",
            )
        except Exception as exc:
            # exc_type only: a driver error message can carry the DSN.
            _logger.warning(
                "prompt_store_unavailable",
                prompt_name=name,
                exc_type=type(exc).__name__,
            )
            return inline_snapshot(name, default)
