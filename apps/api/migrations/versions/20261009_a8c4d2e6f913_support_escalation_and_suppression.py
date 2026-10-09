"""support escalation and notification suppression (P15.S4.T1/T2)

Revision ID: a8c4d2e6f913
Revises: 7f3e2a91c4d6
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a8c4d2e6f913"
down_revision = "7f3e2a91c4d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("support_ticket", sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("support_ticket", sa.Column("escalated_by", sa.UUID(), nullable=True))
    op.add_column("support_ticket", sa.Column("escalation_reason", sa.Text(), nullable=True))
    op.create_foreign_key(None, "support_ticket", "app_user", ["escalated_by"], ["id"], ondelete="RESTRICT")
    op.create_table(
        "notification_suppression",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(length=8), nullable=False),
        sa.Column("destination_hash", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("channel in ('email','push','sms')", name="notification_suppression_channel"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "destination_hash", name="uq_notification_suppression"),
    )


def downgrade() -> None:
    op.drop_table("notification_suppression")
    op.drop_constraint("support_ticket_escalated_by_fkey", "support_ticket", type_="foreignkey")
    op.drop_column("support_ticket", "escalation_reason")
    op.drop_column("support_ticket", "escalated_by")
    op.drop_column("support_ticket", "escalated_at")
