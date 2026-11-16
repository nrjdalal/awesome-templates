"""Prompt store: registry, repository, write rules and the DB provider (#451).

Runs against the shared ``test_db`` fixture (SQLite in-memory by default,
PostgreSQL under ``make test-pg``), so the unique constraint that guards the
append-only numbering is exercised on both engines CI runs.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from src._core.domain.protocols.prompt_provider_protocol import (
    PromptProviderProtocol,
)
from src._core.infrastructure.prompt import registry
from src._core.infrastructure.prompt.db_prompt_provider import DbPromptProvider
from src._core.infrastructure.prompt.models.prompt_model import PromptVersionModel
from src._core.infrastructure.prompt.repository import PromptStoreRepository
from src._core.infrastructure.prompt.service import (
    PromptActiveChanged,
    PromptContentInvalid,
    PromptNotEditable,
    PromptStoreService,
    PromptVersionNotFound,
)

_DEFAULT = "You are the code persona."


@pytest.fixture
def name() -> str:
    # test_db is shared across tests in a session, so each test gets its own
    # prompt name rather than relying on table cleanup.
    return f"test_prompt_{uuid4().hex[:12]}"


@pytest.fixture(autouse=True)
def _registered(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    # A private copy, so a test registration never leaks into the real one.
    monkeypatch.setattr(registry, "_REGISTRY", {name: _DEFAULT})


@pytest.fixture
def repo(test_db) -> PromptStoreRepository:
    return PromptStoreRepository(test_db)


@pytest.fixture
def service(repo) -> PromptStoreService:
    return PromptStoreService(repo)


# ── Registry ────────────────────────────────────────────────────────────────


def test_registration_is_idempotent_and_rejects_a_second_default(name) -> None:
    registry.register_prompt(name, _DEFAULT)
    with pytest.raises(registry.PromptRegistrationConflict):
        registry.register_prompt(name, "a different default")
    assert dict(registry.registered_prompts()) == {name: _DEFAULT}


def test_both_agents_register_their_code_persona(monkeypatch, name) -> None:
    monkeypatch.undo()  # the real registry, populated at import time
    pytest.importorskip("pydantic")
    from src._core.infrastructure.rag import pydantic_ai_answer_agent as rag
    from src.classification.infrastructure.classifier import (
        pydantic_ai_classifier as clf,
    )

    prompts = registry.registered_prompts()
    assert prompts["docs_answer"] == rag._PERSONA  # noqa: SLF001
    assert prompts["classification"] == clf._PERSONA  # noqa: SLF001


# ── Write rules ─────────────────────────────────────────────────────────────


async def test_save_appends_and_never_changes_what_is_served(service, repo, name):
    first = await service.save_version(name, "v1 text", "alice")
    second = await service.save_version(name, "v2 text", "bob")

    assert (first.version, second.version) == (1, 2)
    assert [v.version for v in await service.list_versions(name)] == [2, 1]
    # Saving is inert: nothing is active until someone activates.
    assert await repo.get_active(name) is None


async def test_version_text_is_never_rewritten(service, test_db, name):
    await service.save_version(name, "original", "alice")
    await service.save_version(name, "edited", "alice")
    async with test_db.session() as session:
        rows = (
            await session.execute(
                select(PromptVersionModel.version, PromptVersionModel.content)
                .where(PromptVersionModel.name == name)
                .order_by(PromptVersionModel.version)
            )
        ).all()
    assert [tuple(r) for r in rows] == [(1, "original"), (2, "edited")]


@pytest.mark.parametrize(
    ("registered", "content", "error"),
    [
        (False, "text", PromptNotEditable),
        (True, "", PromptContentInvalid),
        (True, "   \n ", PromptContentInvalid),
        (True, "x" * (registry.MAX_PROMPT_LENGTH + 1), PromptContentInvalid),
    ],
)
async def test_save_rejects(
    service, name: str, registered: bool, content: str, error: type
) -> None:
    target = name if registered else "not_registered"
    with pytest.raises(error):
        await service.save_version(target, content, "alice")


async def test_save_accepts_exactly_the_length_cap(service, name) -> None:
    saved = await service.save_version(name, "x" * registry.MAX_PROMPT_LENGTH, "a")
    assert saved.version == 1


async def test_activate_rollback_and_revert(service, repo, name) -> None:
    await service.save_version(name, "v1 text", "alice")
    await service.save_version(name, "v2 text", "alice")

    await service.activate(name, 2, "alice", expected_active=None)
    active_v2 = await repo.get_active(name)
    assert active_v2 is not None and active_v2.content == "v2 text"

    # A rollback is activating an older version.
    await service.activate(name, 1, "bob", expected_active=2)
    active = await repo.get_active(name)
    assert active is not None
    assert (active.version, active.content, active.activated_by) == (
        1,
        "v1 text",
        "bob",
    )

    await service.revert_to_code_default(name, expected_active=1)
    assert await repo.get_active(name) is None


async def test_activate_unknown_version_is_refused(service, name) -> None:
    await service.save_version(name, "v1 text", "alice")
    with pytest.raises(PromptVersionNotFound):
        await service.activate(name, 7, "alice", expected_active=None)


async def test_stale_page_cannot_overwrite_a_colleagues_change(service, name) -> None:
    await service.save_version(name, "v1", "alice")
    await service.save_version(name, "v2", "alice")
    # Both operators load the page while nothing is active...
    await service.activate(name, 2, "bob", expected_active=None)
    # ...alice's page still believes nothing is active.
    with pytest.raises(PromptActiveChanged):
        await service.activate(name, 1, "alice", expected_active=None)
    with pytest.raises(PromptActiveChanged):
        await service.revert_to_code_default(name, expected_active=None)


# ── DB provider ─────────────────────────────────────────────────────────────


async def test_provider_serves_code_default_when_nothing_is_active(repo, name) -> None:
    provider = DbPromptProvider(repo)
    assert isinstance(provider, PromptProviderProtocol)
    snapshot = await provider.get_active(name, default=_DEFAULT)
    assert (snapshot.content, snapshot.source, snapshot.version) == (
        _DEFAULT,
        "inline",
        None,
    )


async def test_provider_serves_the_active_version_on_the_next_call(
    service, repo, name
) -> None:
    provider = DbPromptProvider(repo)
    await service.save_version(name, "operator text", "alice")
    await service.activate(name, 1, "alice", expected_active=None)

    snapshot = await provider.get_active(name, default=_DEFAULT)
    assert snapshot.content == "operator text"
    assert snapshot.source == "self"
    assert snapshot.version == "1"
    assert snapshot.external_ref == f"{name}@1"

    # No cache: a rollback is visible on the very next call.
    await service.save_version(name, "second text", "alice")
    await service.activate(name, 2, "alice", expected_active=1)
    assert (await provider.get_active(name, default=_DEFAULT)).version == "2"


async def test_provider_degrades_when_the_store_fails(name) -> None:
    from structlog.testing import capture_logs

    class _Broken(PromptStoreRepository):
        def __init__(self) -> None:
            pass

        async def get_active(self, name: str) -> Any:
            raise RuntimeError("could not connect to postgresql://u:secret@db/x")

    with capture_logs() as logs:
        snapshot = await DbPromptProvider(_Broken()).get_active(name, default=_DEFAULT)

    assert (snapshot.content, snapshot.source) == (_DEFAULT, "inline")
    event = next(e for e in logs if e["event"] == "prompt_store_unavailable")
    assert event["exc_type"] == "RuntimeError"
    assert "secret" not in repr(logs)


async def test_unique_constraint_rejects_a_duplicate_number(service, test_db, name):
    """The race guard: two saves that compute the same next number collide."""
    from src._core.exceptions.base_exception import BaseCustomException

    await service.save_version(name, "v1", "alice")
    with pytest.raises(BaseCustomException):
        async with test_db.session() as session:
            session.add(
                PromptVersionModel(name=name, version=1, content="dup", created_by="b")
            )
            await session.commit()
    # And no code path updates text in place: an UPDATE is possible only by
    # hand-written SQL, which the repository does not contain.
    assert not hasattr(PromptStoreRepository, "update_version")
    _ = update  # imported to document the absence above


# ── Review round 1 (#451) ───────────────────────────────────────────────────


async def _force_active(test_db, name: str, version: int, content: str | None) -> None:
    """Write store rows around the service, as hand-edited data would."""
    from src._core.infrastructure.prompt.models.prompt_model import PromptActiveModel

    async with test_db.session() as session:
        if content is not None:
            session.add(
                PromptVersionModel(
                    name=name, version=version, content=content, created_by="sql"
                )
            )
        session.add(PromptActiveModel(name=name, version=version, activated_by="sql"))
        await session.commit()


async def test_corrupt_stored_text_degrades_instead_of_failing(repo, test_db, name):
    from structlog.testing import capture_logs

    await _force_active(test_db, name, 1, "")  # empty text the service would refuse
    with capture_logs() as logs:
        snapshot = await DbPromptProvider(repo).get_active(name, default=_DEFAULT)

    assert (snapshot.content, snapshot.source) == (_DEFAULT, "inline")
    assert any(e["event"] == "prompt_store_unavailable" for e in logs)


async def test_dangling_pointer_is_reported_not_silently_ignored(repo, test_db, name):
    from structlog.testing import capture_logs

    await _force_active(test_db, name, 7, None)  # pointer, no version row
    with capture_logs() as logs:
        snapshot = await DbPromptProvider(repo).get_active(name, default=_DEFAULT)

    assert snapshot.source == "inline"
    event = next(e for e in logs if e["event"] == "prompt_store_unavailable")
    assert event["exc_type"] == "DanglingActivePointer"
