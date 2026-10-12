"""product, product_price: sellable products and append-only price versions (P14.S1.T1, PRODUCTS-01)

Revision ID: c7e2f9a4b815
Revises: a1d7e4b9c602
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c7e2f9a4b815"
down_revision = "a1d7e4b9c602"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("duration_days", sa.SmallInteger(), nullable=False),
        sa.Column("written_units", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind in ('platform', 'subject_package', 'exam_package', 'bundle')", name="product_kind"),
        sa.CheckConstraint("status in ('draft', 'active', 'retired')", name="product_status"),
        sa.CheckConstraint("duration_days between 1 and 366", name="product_duration"),
        sa.CheckConstraint("written_units >= 0", name="product_written_units"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "product_price",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(length=8), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("on_sale", sa.Boolean(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("set_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("channel in ('web')", name="product_price_channel"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="product_price_currency"),
        sa.CheckConstraint("(on_sale and amount_minor is not null) or not on_sale", name="product_price_on_sale"),
        sa.CheckConstraint("amount_minor is null or amount_minor >= 0", name="product_price_amount"),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["set_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_price_current", "product_price", ["product_id", "channel", "starts_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_product_price_current", table_name="product_price")
    op.drop_table("product_price")
    op.drop_table("product")
