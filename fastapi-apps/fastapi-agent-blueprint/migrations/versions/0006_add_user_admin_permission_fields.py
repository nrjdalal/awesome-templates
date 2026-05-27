"""user: add password_temporary, is_bootstrap_admin, permissions for admin permission model

Revision ID: 0006_add_user_admin_permission_fields
Revises: 0005_add_user_role
Create Date: 2026-05-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_add_user_admin_permission_fields"
down_revision: str | None = "0005_add_user_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Step 1: add columns as nullable (portable across SQLite/PostgreSQL/MySQL)
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column("password_temporary", sa.Boolean(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("is_bootstrap_admin", sa.Boolean(), nullable=True)
        )
        batch_op.add_column(sa.Column("permissions", sa.JSON(), nullable=True))

    # Step 2: backfill defaults before applying NOT NULL constraint
    op.execute(
        'UPDATE "user" SET password_temporary = false WHERE password_temporary IS NULL'
    )
    op.execute(
        'UPDATE "user" SET is_bootstrap_admin = false WHERE is_bootstrap_admin IS NULL'
    )
    op.execute("UPDATE \"user\" SET permissions = '[]' WHERE permissions IS NULL")

    # Step 3: set NOT NULL now that all rows have values
    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column("password_temporary", nullable=False)
        batch_op.alter_column("is_bootstrap_admin", nullable=False)
        # permissions stays nullable — an empty JSON list is the semantic default


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("permissions")
        batch_op.drop_column("is_bootstrap_admin")
        batch_op.drop_column("password_temporary")
