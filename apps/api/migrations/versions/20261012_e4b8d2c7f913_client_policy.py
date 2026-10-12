"""client_version_policy, client_manifest: supported app versions and build capability manifests (P13.S1.T4, CLIENTS-01)

Revision ID: e4b8d2c7f913
Revises: d9a3c6e1f472
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e4b8d2c7f913"
down_revision = "d9a3c6e1f472"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_manifest",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(length=10), nullable=False),
        sa.Column("app_version", sa.String(length=20), nullable=False),
        sa.Column("renderer_version", sa.Integer(), nullable=False),
        sa.Column("pack_format_version", sa.Integer(), nullable=False),
        sa.Column("block_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("equation_renderer", sa.String(length=40), nullable=True),
        sa.Column("font_set", sa.String(length=80), nullable=True),
        sa.Column("registered_by", sa.UUID(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["registered_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "app_version", name="uq_client_manifest"),
    )
    op.create_table(
        "client_version_policy",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(length=10), nullable=False),
        sa.Column("min_version", sa.String(length=20), nullable=False),
        sa.Column("notice_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enforce_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("set_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["set_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_client_version_policy_platform"), "client_version_policy", ["platform"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_client_version_policy_platform"), table_name="client_version_policy")
    op.drop_table("client_version_policy")
    op.drop_table("client_manifest")
