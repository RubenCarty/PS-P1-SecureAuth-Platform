"""add simulated payment data

Revision ID: 6f7ff72e7eab
Revises: 6cc218a9df94
"""

from alembic import op
import sqlalchemy as sa


revision = "6f7ff72e7eab"
down_revision = "6cc218a9df94"
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
        "orders",
        schema=None,
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "payment_method",
                sa.String(length=30),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "payment_provider",
                sa.String(length=30),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "payment_last4",
                sa.String(length=4),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "payment_reference",
                sa.String(length=40),
                nullable=True,
            )
        )

        batch_op.create_unique_constraint(
            "uq_orders_payment_reference",
            ["payment_reference"],
        )


def downgrade():
    with op.batch_alter_table(
        "orders",
        schema=None,
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(
            "uq_orders_payment_reference",
            type_="unique",
        )

        batch_op.drop_column(
            "payment_reference"
        )

        batch_op.drop_column(
            "payment_last4"
        )

        batch_op.drop_column(
            "payment_provider"
        )

        batch_op.drop_column(
            "payment_method"
        )