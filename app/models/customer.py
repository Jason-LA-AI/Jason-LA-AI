"""Customer database model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Index, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.lead import Lead
    from app.models.order import Order


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Reusable customer contact and communication profile."""

    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "primary_contact_type IN "
            "('phone', 'xiaohongshu', 'facebook', 'email', 'wechat', 'other')",
            name="ck_customers_primary_contact_type",
        ),
        CheckConstraint(
            "source IN "
            "('XIAOHONGSHU', 'FACEBOOK', 'GOOGLE_WEBSITE', "
            "'REFERRAL', 'OTHER', 'UNKNOWN')",
            name="ck_customers_source",
        ),
        CheckConstraint(
            "preferred_language IS NULL OR preferred_language IN "
            "('English', 'zh-CN', 'zh-TW')",
            name="ck_customers_preferred_language",
        ),
        CheckConstraint(
            "profile_status IN ('ACTIVE', 'INACTIVE')",
            name="ck_customers_profile_status",
        ),
        CheckConstraint(
            "typical_passenger_count IS NULL OR typical_passenger_count >= 0",
            name="ck_customers_typical_passenger_count",
        ),
        Index(
            "ix_customers_contact_type_contact",
            "primary_contact_type",
            "primary_contact",
        ),
    )

    display_name: Mapped[str | None] = mapped_column(String(150))
    primary_contact: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_contact_type: Mapped[str] = mapped_column(String(30), nullable=False)
    secondary_contact: Mapped[str | None] = mapped_column(String(255))
    preferred_contact_method: Mapped[str | None] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    source_detail: Mapped[str | None] = mapped_column(String(255))
    referrer_name: Mapped[str | None] = mapped_column(String(150))
    preferred_language: Mapped[str | None] = mapped_column(String(10))
    preferred_form_of_address: Mapped[str | None] = mapped_column(String(100))
    follow_up_preference: Mapped[str | None] = mapped_column(Text)
    communication_notes: Mapped[str | None] = mapped_column(Text)
    common_pickup_area: Mapped[str | None] = mapped_column(String(255))
    common_destination: Mapped[str | None] = mapped_column(String(255))
    typical_passenger_count: Mapped[int | None] = mapped_column(SmallInteger)
    typical_luggage_details: Mapped[str | None] = mapped_column(Text)
    profile_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    leads: Mapped[list["Lead"]] = relationship(back_populates="customer")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="customer")
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
