"""admin_identity: separate admin identity store + token realm (ADR 049, #218)

Creates the admin_identity + admin_refresh_token tables, moves existing
role='admin' rows out of the user table, then drops the admin-only columns
(role, permissions, password_temporary, is_bootstrap_admin) from user.

Revision ID: 0009_admin_identity_realm_separation
Revises: 0008_ai_usage_add_guardrail_triggered
Create Date: 2026-06-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_admin_identity_realm_separation"
down_revision: str | None = "0008_ai_usage_add_guardrail_triggered"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) admin identity store
    op.create_table(
        "admin_identity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=20), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=True),
        sa.Column(
            "password_temporary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "is_bootstrap_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_admin_identity_username"),
        sa.UniqueConstraint("email", name="uq_admin_identity_email"),
    )

    # 2) admin refresh token store (separate realm)
    op.create_table(
        "admin_refresh_token",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["admin_id"], ["admin_identity.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti", name="uq_admin_refresh_token_jti"),
    )
    op.create_index(
        "ix_admin_refresh_token_admin_expires",
        "admin_refresh_token",
        ["admin_id", "expires_at"],
    )

    # 3) Move existing admins out of the user table into admin_identity.
    #    Preserve id + timestamps: any in-flight NiceGUI admin session stores the
    #    old user.id and re-fetches the admin by it (refresh_session), so a
    #    re-keyed id would resolve a stale cookie to a DIFFERENT admin. Keeping
    #    the id stable makes the realm move transparent to live sessions and
    #    keeps the downgrade faithful.
    op.execute(
        """
        INSERT INTO admin_identity (
            id, username, full_name, email, password,
            permissions, password_temporary, is_bootstrap_admin,
            created_at, updated_at
        )
        SELECT id, username, full_name, email, password,
               permissions, password_temporary, is_bootstrap_admin,
               created_at, updated_at
        FROM "user"
        WHERE role = 'admin'
        """
    )
    # Advance the PK sequence past the migrated ids (Postgres only; SQLite/MySQL
    # derive the next autoincrement from MAX(id) automatically).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "SELECT setval(pg_get_serial_sequence('admin_identity', 'id'), "
            "COALESCE((SELECT MAX(id) FROM admin_identity), 1))"
        )

    # 4) Remove the migrated admins from the user table. Their customer
    #    refresh_token rows (if any) cascade away via the FK.
    op.execute('DELETE FROM "user" WHERE role = \'admin\'')

    # 5) Drop the admin-only columns from user (batch mode for SQLite).
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("permissions")
        batch_op.drop_column("is_bootstrap_admin")
        batch_op.drop_column("password_temporary")
        batch_op.drop_column("role")


def downgrade() -> None:
    # 1) Re-add the admin-only columns on user (nullable → backfill → constrain).
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column("password_temporary", sa.Boolean(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("is_bootstrap_admin", sa.Boolean(), nullable=True)
        )
        batch_op.add_column(sa.Column("permissions", sa.JSON(), nullable=True))

    op.execute("UPDATE \"user\" SET role = 'user' WHERE role IS NULL")
    op.execute(
        'UPDATE "user" SET password_temporary = false WHERE password_temporary IS NULL'
    )
    op.execute(
        'UPDATE "user" SET is_bootstrap_admin = false WHERE is_bootstrap_admin IS NULL'
    )
    op.execute("UPDATE \"user\" SET permissions = '[]' WHERE permissions IS NULL")

    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column(
            "role", nullable=False, server_default="user"
        )
        batch_op.alter_column("password_temporary", nullable=False)
        batch_op.alter_column("is_bootstrap_admin", nullable=False)

    # 2) Move admins back into the user table (id + timestamps preserved).
    op.execute(
        """
        INSERT INTO "user" (
            id, username, full_name, email, password,
            role, permissions, password_temporary, is_bootstrap_admin,
            created_at, updated_at
        )
        SELECT id, username, full_name, email, password,
               'admin', permissions, password_temporary, is_bootstrap_admin,
               created_at, updated_at
        FROM admin_identity
        """
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "SELECT setval(pg_get_serial_sequence('user', 'id'), "
            "COALESCE((SELECT MAX(id) FROM \"user\"), 1))"
        )

    # 3) Drop the admin realm tables.
    op.drop_index(
        "ix_admin_refresh_token_admin_expires", table_name="admin_refresh_token"
    )
    op.drop_table("admin_refresh_token")
    op.drop_table("admin_identity")
