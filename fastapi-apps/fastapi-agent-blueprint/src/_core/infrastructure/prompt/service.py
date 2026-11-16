"""Write rules for the prompt store (#451, ADR 066 Decision 5).

Every rule that keeps the store from becoming "a DB row editor" (ADR 046 §3)
lives here, below the admin page, so a second caller cannot skip them:

- only code-registered names are editable;
- content is non-empty and within ``MAX_PROMPT_LENGTH``;
- saving appends a version and never changes what agents serve;
- activating requires the version to exist, and is refused when the active
  version moved since the operator loaded the page (optimistic check).

Auditing stays with the admin page, next to the session that knows the actor —
the same split the accounts page uses.
"""

from __future__ import annotations

from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.prompt.dtos.prompt_dto import (
    ActivePromptDTO,
    PromptVersionDTO,
)
from src._core.infrastructure.prompt.registry import MAX_PROMPT_LENGTH, is_registered
from src._core.infrastructure.prompt.repository import PromptStoreRepository


class PromptNotEditable(BaseCustomException):
    def __init__(self, name: str) -> None:
        super().__init__(
            status_code=400,
            message=f"Prompt '{name}' is not registered by code and cannot be edited",
            error_code="PROMPT_NOT_EDITABLE",
        )


class PromptContentInvalid(BaseCustomException):
    def __init__(self, reason: str) -> None:
        super().__init__(
            status_code=400, message=reason, error_code="PROMPT_CONTENT_INVALID"
        )


class PromptVersionNotFound(BaseCustomException):
    def __init__(self, name: str, version: int) -> None:
        super().__init__(
            status_code=404,
            message=f"Prompt '{name}' has no version {version}",
            error_code="PROMPT_VERSION_NOT_FOUND",
        )


class PromptActiveChanged(BaseCustomException):
    """Someone else activated or reverted since this operator loaded the page."""

    def __init__(self, name: str) -> None:
        super().__init__(
            status_code=409,
            message=(
                f"The active version of '{name}' changed since this page was "
                "loaded. Reload and try again."
            ),
            error_code="PROMPT_ACTIVE_CHANGED",
        )


class PromptStoreService:
    def __init__(self, repository: PromptStoreRepository) -> None:
        self._repository = repository

    # ── Read (pass-through; the admin page holds a service, never a repo) ──

    async def get_active(self, name: str) -> ActivePromptDTO | None:
        return await self._repository.get_active(name)

    async def list_versions(self, name: str) -> list[PromptVersionDTO]:
        return await self._repository.list_versions(name)

    # ── Write ─────────────────────────────────────────────────────────────

    @staticmethod
    def _require_registered(name: str) -> None:
        if not is_registered(name):
            raise PromptNotEditable(name)

    async def save_version(
        self, name: str, content: str, created_by: str
    ) -> PromptVersionDTO:
        self._require_registered(name)
        if not content.strip():
            raise PromptContentInvalid("Prompt text must not be empty")
        if len(content) > MAX_PROMPT_LENGTH:
            raise PromptContentInvalid(
                f"Prompt text is {len(content)} characters; "
                f"the limit is {MAX_PROMPT_LENGTH}"
            )
        return await self._repository.append_version(name, content, created_by)

    async def activate(
        self,
        name: str,
        version: int,
        activated_by: str,
        *,
        expected_active: int | None,
    ) -> None:
        """Point ``name`` at ``version``. Also how a rollback is done."""
        self._require_registered(name)
        if not await self._repository.version_exists(name, version):
            raise PromptVersionNotFound(name, version)
        await self._check_unchanged(name, expected_active)
        await self._repository.set_active(name, version, activated_by)

    async def revert_to_code_default(
        self, name: str, *, expected_active: int | None
    ) -> None:
        """Clear the pointer, so agents serve the code text again."""
        self._require_registered(name)
        await self._check_unchanged(name, expected_active)
        await self._repository.clear_active(name)

    async def _check_unchanged(self, name: str, expected_active: int | None) -> None:
        # Check-then-write, not a transaction: two operators clicking within
        # the same few milliseconds can both pass. The check exists for the
        # common case — a page left open while a colleague rolled back — and
        # the audit log records both writes either way (ADR 066 Decision 5
        # defers full concurrent-edit handling).
        current = await self._repository.get_active_version(name)
        if current != expected_active:
            raise PromptActiveChanged(name)
