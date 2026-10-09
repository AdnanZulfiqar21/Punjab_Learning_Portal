"""support assisted access (P15.S3.T3)

Revision ID: e2a9b4c7d613
Revises: c5e1f7a2b384
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e2a9b4c7d613"
down_revision = "c5e1f7a2b384"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_assisted_access",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("staff_id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["staff_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_ticket.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_support_assisted_access_user_id"), "support_assisted_access", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_support_assisted_access_user_id"), table_name="support_assisted_access")
    op.drop_table("support_assisted_access")
