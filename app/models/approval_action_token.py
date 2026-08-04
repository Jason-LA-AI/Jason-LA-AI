"""One-time approval action credential database model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ApprovalActionToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hashed, expiring credential for one future approval action."""

    __tablename__ = "approval_action_tokens"
    __table_args__ = (
        CheckConstraint(
            "action IN ('APPROVE', 'DECLINE')",
            name="ck_approval_action_tokens_action",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'USED', 'EXPIRED')",
            name="ck_approval_action_tokens_status",
        ),
        Index("ix_approval_action_tokens_approval_id", "approval_id"),
        Index(
            "uq_approval_action_tokens_token_hash",
            "token_hash",
            unique=True,
        ),
    )

    approval_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("approvals.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
