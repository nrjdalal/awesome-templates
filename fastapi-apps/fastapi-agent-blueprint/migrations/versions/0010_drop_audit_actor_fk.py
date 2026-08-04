"""admin_audit_log: drop the actor foreign key (ADR 057, #348)

Revision ID: 0010_drop_audit_actor_fk
Revises: 0009_admin_identity_realm
Create Date: 2026-08-04

``admin_audit_log.admin_user_id`` carried ``FOREIGN KEY (admin_user_id)
REFERENCES "user" (id) ON DELETE SET NULL`` from 0007. Since ADR 049 / #218 the
value written there is an ``admin_identity.id``, so on PostgreSQL and MySQL every
authenticated admin action failed the constraint and ``AdminAuditLogger``
swallowed it — the audit trail recorded rejected logins (which pass NULL) and
nothing else.

Repointing the constraint at ``admin_identity.id`` was rejected. 0009 copied
admins across preserving their ids and advanced only ``admin_identity``'s
sequence, so the two id spaces overlap: a constraint against either table can be
satisfied by the *wrong* row and assert that a customer performed an admin
action. ``ON DELETE SET NULL`` also let a non-audit path rewrite append-only
evidence, and 0009's ``DELETE FROM "user" WHERE role = 'admin'`` already did
exactly that on engines that enforce foreign keys.

Zero-downtime note (ADR 056): dropping a constraint takes a brief ACCESS
EXCLUSIVE lock on the table and no rewrite, and nothing reads ``admin_user_id``
relationally, so old and new application versions both keep working across the
deploy — the old one simply stops having its inserts rejected.

Data left as found, deliberately. Pre-#218 rows on PostgreSQL/MySQL already had
``admin_user_id`` nulled by 0009's cascade; the same rows on SQLite still hold
the old customer ids. Backfilling would mean guessing which id space a value
came from. ``admin_username`` is the durable reference and is unaffected.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.types import JSON

revision: str = "0010_drop_audit_actor_fk"
down_revision: str | None = "0009_admin_identity_realm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "admin_audit_log"
_COLUMN = "admin_user_id"

# 0007 created the constraint unnamed, so the name is whatever the backend
# generated. Resolving it from the inspector keeps this revision correct on a
# database created by 0007 as well as one created by `Base.metadata.create_all`.
_COMMENT = (
    "admin_identity.id of the actor. Realm-scoped and correlation-only:"
    " never join to user. admin_username is the durable reference."
)


def _audit_table(*, with_actor_fk: bool) -> sa.Table:
    """The 0009 table shape, with or without the actor foreign key.

    SQLite cannot drop or add a constraint in place, and ``batch_alter_table``
    rebuilds from the **reflected** schema — not from the ORM model — so a bare
    ``alter_column`` carries the old ``FOREIGN KEY`` straight into the new table.
    ``copy_from`` has to describe the intended shape.

    Everything the rebuild must preserve has to be declared here, indexes
    included. Omitting them silently drops all four: verified by running the
    revision against SQLite, where ``sqlite_master`` went from four ``idx_audit_*``
    rows to zero. They back the repository's time-ordered list and its
    actor/action/domain filters.

    Declared inline rather than imported from ``AdminAuditLog``: a revision must
    describe the schema at *this* point in history, and the model will keep
    moving.

    Dropping the FK on SQLite matters even though SQLite does not enforce foreign
    keys by default — leaving it in the DDL means enabling
    ``PRAGMA foreign_keys=ON`` would resurrect the defect this revision removes.
    """
    columns: list[sa.SchemaItem] = [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            _COLUMN,
            sa.Integer(),
            nullable=True,
            comment=None if with_actor_fk else _COMMENT,
        ),
        sa.Column("admin_username", sa.String(255), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("record_id", sa.String(128), nullable=True),
        sa.Column("before_state", JSON, nullable=True),
        sa.Column("after_state", JSON, nullable=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("correlation_id", sa.String(36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("idx_audit_created_at", "created_at"),
        sa.Index("idx_audit_user_created", "admin_username", "created_at"),
        sa.Index("idx_audit_action_created", "action", "created_at"),
        sa.Index("idx_audit_domain_created", "domain", "created_at"),
    ]
    if with_actor_fk:
        columns.append(
            sa.ForeignKeyConstraint([_COLUMN], ["user.id"], ondelete="SET NULL")
        )
    return sa.Table(_TABLE, sa.MetaData(), *columns)


def _actor_fk_name(bind) -> str | None:
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(_TABLE):
        if fk.get("constrained_columns") == [_COLUMN]:
            return fk.get("name")
    return None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        # copy_from is required — see _table_without_actor_fk. Without it the
        # rebuild reflects the old FOREIGN KEY back into the new table.
        with op.batch_alter_table(
            _TABLE, copy_from=_audit_table(with_actor_fk=False)
        ) as batch_op:
            batch_op.alter_column(_COLUMN, existing_type=sa.Integer(), comment=_COMMENT)
        return

    name = _actor_fk_name(bind)
    if name:
        op.drop_constraint(name, _TABLE, type_="foreignkey")

    op.alter_column(_TABLE, _COLUMN, existing_type=sa.Integer(), comment=_COMMENT)


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        # Rebuild *with* the constraint. Only removing the comment would leave
        # the downgrade asymmetric with the other engines and, worse, silently
        # non-reversible: the foreign key this revision removed would stay gone.
        with op.batch_alter_table(
            _TABLE, copy_from=_audit_table(with_actor_fk=True)
        ) as batch_op:
            batch_op.alter_column(_COLUMN, existing_type=sa.Integer(), comment=None)
        return

    op.alter_column(_TABLE, _COLUMN, existing_type=sa.Integer(), comment=None)

    # Restoring the constraint can fail on real data: any row whose
    # admin_user_id is an admin_identity.id with no matching user row will
    # violate it. That is the defect this revision removed, and a faithful
    # downgrade has to reintroduce it rather than silently drop the rows.
    op.create_foreign_key(
        "admin_audit_log_admin_user_id_fkey",
        _TABLE,
        "user",
        [_COLUMN],
        ["id"],
        ondelete="SET NULL",
    )
