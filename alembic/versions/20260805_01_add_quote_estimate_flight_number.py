"""Add optional flight number to quote estimates.

Revision ID: 20260805_01
Revises: 20260803_01
Create Date: 2026-08-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260805_01"
down_revision: str | None = "20260803_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist optional flight numbers with quote estimates."""

    op.add_column(
        "quote_estimates",
        sa.Column("flight_number", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    """Remove flight-number persistence from quote estimates."""

    op.drop_column("quote_estimates", "flight_number")
