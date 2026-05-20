"""user: add unique username and email constraints

Revision ID: 0003_user_unique_constraints
Revises: 0002_ai_usage_log
Create Date: 2026-04-30

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_user_unique_constraints"
down_revision: Union[str, None] = "0002_ai_usage_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.create_unique_constraint("uq_user_username", ["username"])
        batch_op.create_unique_constraint("uq_user_email", ["email"])


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_constraint("uq_user_email", type_="unique")
        batch_op.drop_constraint("uq_user_username", type_="unique")
