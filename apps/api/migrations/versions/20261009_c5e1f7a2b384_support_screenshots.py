"""support request screenshots (P15.S3.T1)

Revision ID: c5e1f7a2b384
Revises: a8c4d2e6f913
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c5e1f7a2b384"
down_revision = "a8c4d2e6f913"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_attachment",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("uploaded_by", sa.UUID(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("original_sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_ticket.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_support_attachment_ticket_id"), "support_attachment", ["ticket_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_support_attachment_ticket_id"), table_name="support_attachment")
    op.drop_table("support_attachment")
