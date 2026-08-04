"""The production audit-actor path, asserted on every engine (#348, ADR 057).

This file began as an `xfail(strict=True)` probe. `admin_audit_log.admin_user_id`
carried `ForeignKey("user.id", ondelete="SET NULL")` while the value written at
runtime is an `admin_identity.id`, so on PostgreSQL every authenticated admin
action failed the constraint and `AdminAuditLogger` swallowed it — the trail
recorded rejected logins (which pass NULL) and nothing else.

ADR 057 dropped the constraint rather than repointing it: migration 0009 copied
admins across preserving ids and advanced only `admin_identity`'s sequence, so
the id spaces overlap and a constraint against either table can be satisfied by
the *wrong* row — certifying that a customer performed an admin action.

The xfail is gone; these are now positive assertions. Integrity moved from the
DDL to here, which only works if the tests are the real thing: the actor is a
genuine `admin_identity` row, the write goes through the production repository,
and the stored id is read back and resolved through the `admin_identity`
repository the way `project-dna` §17 IC-218-1 requires ("Cross-realm reads go
only through the owning domain's repository/protocol").

The read-side reconciliation is deliberately a *read*: unlike a foreign key it
cannot reject — and therefore cannot lose — an audit event.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select

from src._core.infrastructure.admin.audit import (
    AdminAction,
    AdminAuditLogRepository,
    AuditLogDTO,
    AuditLogFilter,
    AuditResult,
)
from src._core.infrastructure.admin.audit.models.audit_log_model import AdminAuditLog
from src.admin_identity.infrastructure.database.models.admin_identity_model import (
    AdminIdentityModel,
)
from src.admin_identity.infrastructure.repositories.admin_identity_repository import (
    AdminIdentityRepository,
)
from src.user.infrastructure.database.models.user_model import UserModel

# An explicit, deliberately out-of-range id. With an autoincrement id this test
# is order-dependent and unusable: `tests/conftest.py::test_db` is session-scoped
# and truncates nothing, so whether the new admin's id collides with a `user.id`
# some earlier test happened to create decides whether the FK is satisfied. That
# is not hypothetical — the first version of this file XPASSed in the full suite
# (strict=True turned that into a failure) while xfailing when the package ran
# alone. Nothing in the suite inserts a user this far up.
_PROBE_ADMIN_ID = 900_001


@pytest_asyncio.fixture
async def admin_identity_row(test_db):
    """A real admin whose id is what production would attribute an action to."""
    async with test_db.session() as session:
        colliding_user = (
            await session.execute(
                select(UserModel.id).where(UserModel.id == _PROBE_ADMIN_ID)
            )
        ).scalar_one_or_none()
        assert colliding_user is None, (
            f"a user row exists at id {_PROBE_ADMIN_ID}, which would satisfy the "
            "FK by accident and make this probe meaningless"
        )

        existing = (
            await session.execute(
                select(AdminIdentityModel).where(
                    AdminIdentityModel.id == _PROBE_ADMIN_ID
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing.id

        admin = AdminIdentityModel(
            id=_PROBE_ADMIN_ID,
            username="audit-fk-probe",
            full_name="Audit FK Probe",
            email="audit-fk-probe@example.com",
            password="not-a-real-hash",
        )
        session.add(admin)
        await session.commit()
        return admin.id


@pytest.mark.asyncio
async def test_audit_write_accepts_an_admin_identity_actor(test_db, admin_identity_row):
    repo = AdminAuditLogRepository(test_db)

    await repo.insert(
        AuditLogDTO(
            admin_user_id=admin_identity_row,
            admin_username="audit-fk-probe",
            action=AdminAction.LOGIN,
            domain="auth",
            result=AuditResult.SUCCESS,
        )
    )

    async with test_db.session() as session:
        stored = (
            (
                await session.execute(
                    select(AdminAuditLog).where(
                        AdminAuditLog.admin_username == "audit-fk-probe"
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(stored) == 1
    assert stored[0].admin_user_id == admin_identity_row


@pytest.mark.asyncio
async def test_stored_actor_resolves_through_the_admin_identity_repository(
    test_db, admin_identity_row
):
    """The reconciliation that replaces the dropped foreign key.

    A FK asserted "this id exists in some table" at write time, and paid for it
    by being able to reject — and, given the swallow, silently lose — the event.
    This asserts the stronger property on the read side instead: the id stored
    in an audit row resolves to a real admin *in the owning context's own
    repository*, which is the access path §17 IC-218-1 mandates.
    """
    repo = AdminAuditLogRepository(test_db)
    await repo.insert(
        AuditLogDTO(
            admin_user_id=admin_identity_row,
            admin_username="audit-fk-probe",
            action=AdminAction.ACCOUNT_CREATE,
            domain="admin_identity",
            result=AuditResult.SUCCESS,
        )
    )

    rows, _ = await repo.list_filtered(AuditLogFilter(username_like="audit-fk-probe"))
    actor_ids = {r.admin_user_id for r in rows if r.admin_user_id is not None}
    assert actor_ids, "the audit row stored no actor id to reconcile"

    admin_repository = AdminIdentityRepository(test_db)
    for actor_id in actor_ids:
        # select_data_by_id raises 404 rather than returning None, so an
        # unresolvable actor fails this test loudly instead of via a None check.
        assert await admin_repository.exists_by_id(actor_id), (
            f"audit row references admin_identity id {actor_id}, which does not "
            "resolve through the admin_identity repository"
        )
        resolved = await admin_repository.select_data_by_id(actor_id)
        assert resolved.username == "audit-fk-probe"


@pytest.mark.asyncio
async def test_actor_id_is_not_a_customer_id(test_db, admin_identity_row):
    """The misattribution the dropped FK could have certified.

    Migration 0009 copied admins into admin_identity preserving ids and advanced
    only that table's sequence, so the id spaces overlap. A constraint against
    `user.id` can therefore be *satisfied* by a customer who happens to occupy
    the same id — recording that a customer performed an admin action. Assert
    the column is read as an admin-realm id and nothing else.
    """
    async with test_db.session() as session:
        customer_at_same_id = (
            await session.execute(
                select(UserModel.id).where(UserModel.id == admin_identity_row)
            )
        ).scalar_one_or_none()

    assert customer_at_same_id is None, (
        "a user row shares this id, so any FK to user.id would be satisfied by "
        "the wrong realm — see ADR 057"
    )
