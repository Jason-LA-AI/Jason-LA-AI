"""Create expiring approval action tokens.

Revision ID: dbf9c10a7143
Revises: 20260810_02
Create Date: 2026-08-31
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "dbf9c10a7143"
down_revision: str | None = "20260810_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create hashed, one-time credentials for approval actions."""

    op.create_table(
        "approval_action_tokens",
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="ACTIVE", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("action IN ('APPROVE', 'DECLINE')", name="ck_approval_action_tokens_action"),
        sa.CheckConstraint("status IN ('ACTIVE', 'USED', 'EXPIRED')", name="ck_approval_action_tokens_status"),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["approvals.id"],
            name="fk_approval_action_tokens_approval_id_approvals",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_approval_action_tokens"),
    )
    op.create_index(
        "ix_approval_action_tokens_approval_id",
        "approval_action_tokens",
        ["approval_id"],
        unique=False,
    )
    op.create_index(
        "uq_approval_action_tokens_token_hash",
        "approval_action_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    """Remove approval action credentials."""

    op.drop_index("uq_approval_action_tokens_token_hash", table_name="approval_action_tokens")
    op.drop_index("ix_approval_action_tokens_approval_id", table_name="approval_action_tokens")
    op.drop_table("approval_action_tokens")
