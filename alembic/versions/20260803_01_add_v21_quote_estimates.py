"""Add V2.1 quote estimates and structured quote intake fields.

Revision ID: 20260803_01
Revises: None
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260803_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the V2.1 estimate table and non-destructive intake fields."""

    op.create_table(
        "quote_estimates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="ESTIMATED", nullable=False),
        sa.Column("service_type", sa.String(length=40), nullable=False),
        sa.Column("airport_code", sa.String(length=3), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("service_time", sa.Time(timezone=False), nullable=False),
        sa.Column(
            "service_timezone",
            sa.String(length=50),
            server_default="America/Los_Angeles",
            nullable=False,
        ),
        sa.Column("service_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location_input", sa.String(length=255), nullable=False),
        sa.Column("location_input_type", sa.String(length=20), nullable=False),
        sa.Column("normalized_city", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=10), nullable=True),
        sa.Column("pricing_zone", sa.String(length=50), nullable=True),
        sa.Column("route_summary", sa.String(length=255), nullable=False),
        sa.Column("passenger_count", sa.SmallInteger(), nullable=False),
        sa.Column(
            "passenger_count_is_minimum",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("large_suitcase_count", sa.SmallInteger(), nullable=False),
        sa.Column(
            "large_suitcase_count_is_minimum",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("child_seat_required", sa.String(length=10), nullable=False),
        sa.Column("oversized_items_present", sa.Boolean(), nullable=False),
        sa.Column("estimated_min_amount", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("estimated_max_amount", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("suggested_amount", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("currency_code", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("pricing_source", sa.String(length=100), nullable=True),
        sa.Column("pricing_rule_version", sa.String(length=100), nullable=False),
        sa.Column("pricing_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("vehicle_assessment", sa.String(length=30), nullable=False),
        sa.Column("risk_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("manual_review_reason", sa.Text(), nullable=True),
        sa.Column(
            "requires_jason_review",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('ESTIMATED', 'MANUAL_REVIEW_REQUIRED', 'ACCEPTED', "
            "'CONVERTED', 'EXPIRED', 'INVALIDATED')",
            name="ck_quote_estimates_status",
        ),
        sa.CheckConstraint(
            "service_type IN ('AIRPORT_PICKUP', 'AIRPORT_DROPOFF')",
            name="ck_quote_estimates_service_type",
        ),
        sa.CheckConstraint(
            "airport_code IN ('LAX', 'ONT', 'SNA', 'BUR', 'LGB')",
            name="ck_quote_estimates_airport_code",
        ),
        sa.CheckConstraint(
            "location_input_type IN ('ZIP', 'CITY')",
            name="ck_quote_estimates_location_input_type",
        ),
        sa.CheckConstraint(
            "passenger_count BETWEEN 1 AND 5",
            name="ck_quote_estimates_passenger_count",
        ),
        sa.CheckConstraint(
            "NOT passenger_count_is_minimum OR passenger_count = 5",
            name="ck_quote_estimates_passenger_count_minimum",
        ),
        sa.CheckConstraint(
            "large_suitcase_count BETWEEN 0 AND 4",
            name="ck_quote_estimates_large_suitcase_count",
        ),
        sa.CheckConstraint(
            "NOT large_suitcase_count_is_minimum OR large_suitcase_count = 4",
            name="ck_quote_estimates_large_suitcase_count_minimum",
        ),
        sa.CheckConstraint(
            "child_seat_required IN ('YES', 'NO', 'UNKNOWN')",
            name="ck_quote_estimates_child_seat_required",
        ),
        sa.CheckConstraint(
            "estimated_min_amount IS NULL OR estimated_min_amount >= 0",
            name="ck_quote_estimates_min_amount",
        ),
        sa.CheckConstraint(
            "estimated_max_amount IS NULL OR estimated_max_amount >= 0",
            name="ck_quote_estimates_max_amount",
        ),
        sa.CheckConstraint(
            "suggested_amount IS NULL OR suggested_amount >= 0",
            name="ck_quote_estimates_suggested_amount",
        ),
        sa.CheckConstraint(
            "estimated_min_amount IS NULL OR estimated_max_amount IS NULL "
            "OR estimated_min_amount <= estimated_max_amount",
            name="ck_quote_estimates_amount_range",
        ),
        sa.CheckConstraint(
            "status <> 'ESTIMATED' OR "
            "(estimated_min_amount IS NOT NULL AND estimated_max_amount IS NOT NULL)",
            name="ck_quote_estimates_estimated_amounts_present",
        ),
        sa.CheckConstraint("currency_code = 'USD'", name="ck_quote_estimates_currency_code"),
        sa.CheckConstraint(
            "vehicle_assessment IN ('LIKELY_COMFORTABLE', 'NEEDS_CONFIRMATION', "
            "'NOT_RECOMMENDED', 'INSUFFICIENT_INFORMATION')",
            name="ck_quote_estimates_vehicle_assessment",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_quote_estimates"),
    )
    op.create_index(
        "ix_quote_estimates_status_expires_at",
        "quote_estimates",
        ["status", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_quote_estimates_airport_pricing_zone",
        "quote_estimates",
        ["airport_code", "pricing_zone"],
        unique=False,
    )
    op.create_index(
        "ix_quote_estimates_service_datetime",
        "quote_estimates",
        ["service_datetime"],
        unique=False,
    )

    op.add_column("customers", sa.Column("phone_number", sa.String(length=30), nullable=True))
    op.add_column(
        "customers", sa.Column("phone_number_normalized", sa.String(length=30), nullable=True)
    )
    op.add_column("customers", sa.Column("email", sa.String(length=254), nullable=True))
    op.add_column(
        "customers", sa.Column("email_normalized", sa.String(length=254), nullable=True)
    )
    op.create_index(
        "ix_customers_phone_number_normalized",
        "customers",
        ["phone_number_normalized"],
        unique=False,
        postgresql_where=sa.text("phone_number_normalized IS NOT NULL"),
    )
    op.create_index(
        "ix_customers_email_normalized",
        "customers",
        ["email_normalized"],
        unique=False,
        postgresql_where=sa.text("email_normalized IS NOT NULL"),
    )

    op.add_column(
        "leads",
        sa.Column("intake_method", sa.String(length=40), server_default="FREE_TEXT", nullable=False),
    )
    op.add_column(
        "leads", sa.Column("estimate_accepted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("leads", sa.Column("idempotency_key", sa.String(length=100), nullable=True))
    op.create_check_constraint(
        "ck_leads_intake_method",
        "leads",
        "intake_method IN ('FREE_TEXT', 'STRUCTURED_QUOTE_V2', 'MANUAL', 'DEVELOPMENT_SEED')",
    )
    op.create_index(
        "uq_leads_idempotency_key",
        "leads",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.add_column(
        "orders",
        sa.Column("quote_estimate_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("orders", sa.Column("postal_code", sa.String(length=10), nullable=True))
    op.add_column("orders", sa.Column("pricing_zone", sa.String(length=50), nullable=True))
    op.add_column(
        "orders",
        sa.Column(
            "passenger_count_is_minimum",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "large_suitcase_count_is_minimum",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "orders", sa.Column("oversized_items_present", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "orders",
        sa.Column("customer_estimate_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_orders_quote_estimate_id_quote_estimates",
        "orders",
        "quote_estimates",
        ["quote_estimate_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_orders_passenger_count_minimum",
        "orders",
        "NOT passenger_count_is_minimum OR "
        "(passenger_count IS NOT NULL AND passenger_count = 5)",
    )
    op.create_check_constraint(
        "ck_orders_large_suitcase_count_minimum",
        "orders",
        "NOT large_suitcase_count_is_minimum OR "
        "(large_suitcase_count IS NOT NULL AND large_suitcase_count = 4)",
    )
    op.create_index(
        "uq_orders_quote_estimate_id",
        "orders",
        ["quote_estimate_id"],
        unique=True,
        postgresql_where=sa.text("quote_estimate_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove only the V2.1 estimate table and added intake fields."""

    op.drop_index("uq_orders_quote_estimate_id", table_name="orders")
    op.drop_constraint("ck_orders_large_suitcase_count_minimum", "orders", type_="check")
    op.drop_constraint("ck_orders_passenger_count_minimum", "orders", type_="check")
    op.drop_constraint(
        "fk_orders_quote_estimate_id_quote_estimates", "orders", type_="foreignkey"
    )
    op.drop_column("orders", "customer_estimate_accepted_at")
    op.drop_column("orders", "oversized_items_present")
    op.drop_column("orders", "large_suitcase_count_is_minimum")
    op.drop_column("orders", "passenger_count_is_minimum")
    op.drop_column("orders", "pricing_zone")
    op.drop_column("orders", "postal_code")
    op.drop_column("orders", "quote_estimate_id")

    op.drop_index("uq_leads_idempotency_key", table_name="leads")
    op.drop_constraint("ck_leads_intake_method", "leads", type_="check")
    op.drop_column("leads", "idempotency_key")
    op.drop_column("leads", "estimate_accepted_at")
    op.drop_column("leads", "intake_method")

    op.drop_index("ix_customers_email_normalized", table_name="customers")
    op.drop_index("ix_customers_phone_number_normalized", table_name="customers")
    op.drop_column("customers", "email_normalized")
    op.drop_column("customers", "email")
    op.drop_column("customers", "phone_number_normalized")
    op.drop_column("customers", "phone_number")

    op.drop_index("ix_quote_estimates_service_datetime", table_name="quote_estimates")
    op.drop_index("ix_quote_estimates_airport_pricing_zone", table_name="quote_estimates")
    op.drop_index("ix_quote_estimates_status_expires_at", table_name="quote_estimates")
    op.drop_table("quote_estimates")
