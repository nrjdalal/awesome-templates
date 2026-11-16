"""/admin/prompts write path (#451): permission re-check and auditing."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("nicegui")

from src._apps.admin.pages import prompts  # noqa: E402
from src._core.infrastructure.admin.audit import AdminAction, AuditResult  # noqa: E402


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def log(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class _Button:
    def props(self, *args: Any, **kwargs: Any) -> Any:
        return self


async def test_write_refused_after_permission_revoked_is_audited(monkeypatch):
    audit = _Recorder()
    writes: list[str] = []

    async def no_permission() -> None:
        return None

    async def write(user: str) -> None:
        writes.append(user)

    monkeypatch.setattr(prompts, "_authorised_username", no_permission)
    monkeypatch.setattr(prompts, "get_audit_logger", lambda: audit)

    async def rerender() -> None:
        raise AssertionError("must not re-render on a refused write")

    await prompts._run_write(  # noqa: SLF001
        action=AdminAction.PROMPT_ACTIVATE,
        name="docs_answer",
        button=_Button(),
        write=write,
        record_id=lambda _: "docs_answer@2",
        success="unused",
        rerender=rerender,
    )

    assert writes == []  # refused before any side effect
    assert audit.calls == [
        {
            "action": AdminAction.PROMPT_ACTIVATE,
            "domain": "prompts",
            "record_id": "docs_answer",
            "result": AuditResult.FAILURE,
            "failure_reason": "PERMISSION_DENIED",
        }
    ]
