"""Allow phone and WeChat lead sources.

Revision ID: 20260810_02
Revises: 20260810_01
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260810_02"
down_revision: str | None = "20260810_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_leads_source", "leads", type_="check")
    op.drop_constraint("ck_customers_source", "customers", type_="check")
    _create_source_constraints(include_manual_sources=True)


def downgrade() -> None:
    op.drop_constraint("ck_leads_source", "leads", type_="check")
    op.drop_constraint("ck_customers_source", "customers", type_="check")
    op.execute("UPDATE leads SET source = 'OTHER' WHERE source IN ('PHONE', 'WECHAT')")
    op.execute("UPDATE customers SET source = 'OTHER' WHERE source IN ('PHONE', 'WECHAT')")
    _create_source_constraints(include_manual_sources=False)


def _create_source_constraints(*, include_manual_sources: bool) -> None:
    manual_sources = "'PHONE', 'WECHAT', " if include_manual_sources else ""
    expression = (
        "source IN ('WEBSITE', 'XIAOHONGSHU', 'FACEBOOK', 'GOOGLE', "
        f"{manual_sources}'REFERRAL', 'OTHER', 'UNKNOWN')"
    )
    op.create_check_constraint("ck_leads_source", "leads", expression)
    op.create_check_constraint("ck_customers_source", "customers", expression)
