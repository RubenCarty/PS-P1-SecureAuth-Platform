"""add google authentication fields

Revision ID: c62c48ddbe08
Revises: cb2b1056a393
Create Date: 2026-07-19 12:24:10.286694
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c62c48ddbe08"
down_revision = "cb2b1056a393"
branch_labels = None
depends_on = None


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": (
        "fk_%(table_name)s_%(column_0_name)s_"
        "%(referred_table_name)s"
    ),
    "pk": "pk_%(table_name)s",
}


def upgrade():
    with op.batch_alter_table(
        "users",
        schema=None,
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "google_sub",
                sa.String(length=255),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "banned_reason",
                sa.String(length=300),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "banned_at",
                sa.DateTime(),
                nullable=True,
            )
        )

        batch_op.create_unique_constraint(
            "uq_users_google_sub",
            ["google_sub"],
        )


def downgrade():
    with op.batch_alter_table(
        "users",
        schema=None,
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(
            "uq_users_google_sub",
            type_="unique",
        )

        batch_op.drop_column("banned_at")
        batch_op.drop_column("banned_reason")
        batch_op.drop_column("google_sub")