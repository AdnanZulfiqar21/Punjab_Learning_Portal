"""commerce_terms: owner-reviewed purchase terms, drafted and published by two people (P14.S1.T3, PRICING-01)

Revision ID: d9a3c6e1f472
Revises: c7e2f9a4b815
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d9a3c6e1f472"
down_revision = "c7e2f9a4b815"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commerce_terms",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("tax_note", sa.Text(), nullable=False),
        sa.Column("renewal_note", sa.Text(), nullable=False),
        sa.Column("conversion_note", sa.Text(), nullable=False),
        sa.Column("refund_note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("drafted_by", sa.UUID(), nullable=False),
        sa.Column("drafted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_by", sa.UUID(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('draft', 'published', 'superseded')", name="commerce_terms_status"),
        sa.CheckConstraint("published_by is null or published_by <> drafted_by", name="commerce_terms_two_people"),
        sa.ForeignKeyConstraint(["drafted_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )
    op.create_index(
        "uq_commerce_terms_draft",
        "commerce_terms",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
    )
    op.create_index(
        "uq_commerce_terms_published",
        "commerce_terms",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_commerce_terms_published", table_name="commerce_terms", postgresql_where=sa.text("status = 'published'")
    )
    op.drop_index("uq_commerce_terms_draft", table_name="commerce_terms", postgresql_where=sa.text("status = 'draft'"))
    op.drop_table("commerce_terms")
