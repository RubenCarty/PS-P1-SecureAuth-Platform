"""allow google users without password

Revision ID: 6cc218a9df94
Revises: c62c48ddbe08
Create Date: 2026-07-19 14:04:52.388974
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6cc218a9df94"
down_revision = "c62c48ddbe08"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "users",
        schema=None,
    ) as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=500),
            nullable=True,
        )


def downgrade():
    with op.batch_alter_table(
        "users",
        schema=None,
    ) as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=500),
            nullable=False,
        )