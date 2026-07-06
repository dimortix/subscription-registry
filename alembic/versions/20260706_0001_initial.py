"""initial

Revision ID: 0001
Revises:
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "obligations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "category",
            sa.Enum("subscription", "warranty", "bill", "insurance", name="category"),
            nullable=False,
        ),
        sa.Column(
            "recurrence",
            sa.Enum("monthly", "quarterly", "yearly", name="recurrence"),
            nullable=True,
        ),
        sa.Column("next_payment_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "cancelled", "expired", name="obligation_status"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index("ix_obligations_next_payment_date", "obligations", ["next_payment_date"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "obligation_id",
            sa.Uuid(),
            sa.ForeignKey("obligations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "paid_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index("ix_payments_obligation_id", "payments", ["obligation_id"])


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("obligations")
    sa.Enum(name="obligation_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="recurrence").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="category").drop(op.get_bind(), checkfirst=True)
