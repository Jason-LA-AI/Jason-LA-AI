"""Split website and Google quote-request sources.

Revision ID: 20260810_01
Revises: 20260806_01
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260810_01"
down_revision: str | None = "20260806_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Normalize legacy combined values and allow distinct attribution."""

    op.drop_constraint("ck_leads_source", "leads", type_="check")
    op.drop_constraint("ck_customers_source", "customers", type_="check")
    op.execute("UPDATE leads SET source = 'WEBSITE' WHERE source = 'GOOGLE_WEBSITE'")
    op.execute("UPDATE customers SET source = 'WEBSITE' WHERE source = 'GOOGLE_WEBSITE'")
    op.create_check_constraint(
        "ck_leads_source",
        "leads",
        "source IN ('WEBSITE', 'XIAOHONGSHU', 'FACEBOOK', 'GOOGLE', "
        "'REFERRAL', 'OTHER', 'UNKNOWN')",
    )
    op.create_check_constraint(
        "ck_customers_source",
        "customers",
        "source IN ('WEBSITE', 'XIAOHONGSHU', 'FACEBOOK', 'GOOGLE', "
        "'REFERRAL', 'OTHER', 'UNKNOWN')",
    )


def downgrade() -> None:
    """Merge website and Google attribution for the legacy schema."""

    op.drop_constraint("ck_leads_source", "leads", type_="check")
    op.drop_constraint("ck_customers_source", "customers", type_="check")
    op.execute(
        "UPDATE leads SET source = 'GOOGLE_WEBSITE' "
        "WHERE source IN ('WEBSITE', 'GOOGLE')"
    )
    op.execute(
        "UPDATE customers SET source = 'GOOGLE_WEBSITE' "
        "WHERE source IN ('WEBSITE', 'GOOGLE')"
    )
    op.create_check_constraint(
        "ck_leads_source",
        "leads",
        "source IN ('XIAOHONGSHU', 'FACEBOOK', 'GOOGLE_WEBSITE', "
        "'REFERRAL', 'OTHER', 'UNKNOWN')",
    )
    op.create_check_constraint(
        "ck_customers_source",
        "customers",
        "source IN ('XIAOHONGSHU', 'FACEBOOK', 'GOOGLE_WEBSITE', "
        "'REFERRAL', 'OTHER', 'UNKNOWN')",
    )
