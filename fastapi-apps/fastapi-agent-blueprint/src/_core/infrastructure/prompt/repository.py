"""Prompt store repository (#451, ADR 066).

Not a ``BaseRepository`` subclass, for the same reason as the audit log: the
version table is append-only and the pointer table is a single-row-per-name
upsert. Generic CRUD would expose an ``update`` on version text, which is
exactly what the store must not have.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import delete, func, select

from src._core.infrastructure.persistence.rdb.database import Database
from src._core.infrastructure.prompt.dtos.prompt_dto import (
    ActivePromptDTO,
    PromptVersionDTO,
)
from src._core.infrastructure.prompt.models.prompt_model import (
    PromptActiveModel,
    PromptVersionModel,
)


class DanglingActivePointer(RuntimeError):
    """``prompt_active`` names a version that ``prompt_version`` does not hold.

    The write path cannot produce this (activate checks the version exists and
    versions are never deleted); it means hand-edited or partially restored
    data. Raised rather than read as "nothing active" so the provider logs it.
    """


class PromptStoreRepository:
    def __init__(self, database: Database | Callable[[], Database]) -> None:
        """Accept a ``Database`` or a zero-arg provider returning one.

        ``CoreContainer`` passes its ``database`` *provider*, so
        ``override_database`` (applied after the container is built) is seen
        by every read — the same reason ``AdminAuditLogRepository`` takes one.
        """
        self._database_source = database

    @property
    def _database(self) -> Database:
        source = self._database_source
        return source if isinstance(source, Database) else source()

    # ── Read ────────────────────────────────────────────────────────────────

    async def get_active(self, name: str) -> ActivePromptDTO | None:
        """The active version of ``name`` with its text, or ``None``.

        One indexed join per agent call: ``prompt_active`` is keyed on name,
        and ``prompt_version`` has a unique index on ``(name, version)``.
        """
        stmt = (
            select(
                PromptActiveModel.name,
                PromptActiveModel.version,
                PromptVersionModel.content,
                PromptActiveModel.activated_by,
                PromptActiveModel.activated_at,
            )
            # Outer join: "no pointer" and "pointer to a missing version" must
            # stay distinguishable — the first is normal, the second is not.
            .outerjoin(
                PromptVersionModel,
                (PromptVersionModel.name == PromptActiveModel.name)
                & (PromptVersionModel.version == PromptActiveModel.version),
            )
            .where(PromptActiveModel.name == name)
        )
        async with self._database.session() as session:
            row = (await session.execute(stmt)).one_or_none()
        if row is None:
            return None
        if row.content is None:
            raise DanglingActivePointer(f"{name}@{row.version}")
        return ActivePromptDTO(
            name=row.name,
            version=row.version,
            content=row.content,
            activated_by=row.activated_by,
            activated_at=row.activated_at,
        )

    async def get_active_version(self, name: str) -> int | None:
        stmt = select(PromptActiveModel.version).where(PromptActiveModel.name == name)
        async with self._database.session() as session:
            return (await session.execute(stmt)).scalar_one_or_none()

    async def list_versions(self, name: str) -> list[PromptVersionDTO]:
        """Every version of ``name``, newest first."""
        stmt = (
            select(PromptVersionModel)
            .where(PromptVersionModel.name == name)
            .order_by(PromptVersionModel.version.desc())
        )
        async with self._database.session() as session:
            models = (await session.execute(stmt)).scalars().all()
        return [
            PromptVersionDTO.model_validate(m, from_attributes=True) for m in models
        ]

    async def version_exists(self, name: str, version: int) -> bool:
        stmt = select(func.count()).where(
            PromptVersionModel.name == name, PromptVersionModel.version == version
        )
        async with self._database.session() as session:
            return bool((await session.execute(stmt)).scalar_one())

    # ── Write ───────────────────────────────────────────────────────────────

    async def append_version(
        self, name: str, content: str, created_by: str
    ) -> PromptVersionDTO:
        """Insert ``v(max+1)``. Never updates an existing row.

        Two concurrent saves can compute the same number; the unique constraint
        rejects the second, which surfaces as a ``DatabaseException`` from
        ``Database.session()`` and is reported to the operator as a conflict.
        """
        async with self._database.session() as session:
            current = (
                await session.execute(
                    select(func.max(PromptVersionModel.version)).where(
                        PromptVersionModel.name == name
                    )
                )
            ).scalar_one_or_none()
            model = PromptVersionModel(
                name=name,
                version=(current or 0) + 1,
                content=content,
                created_by=created_by,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
        return PromptVersionDTO.model_validate(model, from_attributes=True)

    async def set_active(self, name: str, version: int, activated_by: str) -> None:
        async with self._database.session() as session:
            existing = await session.get(PromptActiveModel, name)
            if existing is None:
                session.add(
                    PromptActiveModel(
                        name=name, version=version, activated_by=activated_by
                    )
                )
            else:
                existing.version = version
                existing.activated_by = activated_by
                # Naive UTC, matching the `DateTime` column and the ledger.
                existing.activated_at = datetime.now(UTC).replace(tzinfo=None)
            await session.commit()

    async def clear_active(self, name: str) -> None:
        async with self._database.session() as session:
            await session.execute(
                delete(PromptActiveModel).where(PromptActiveModel.name == name)
            )
            await session.commit()
