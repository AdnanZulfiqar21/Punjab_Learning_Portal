"""attempt.holder_session_id: which signed-in device may write to an active attempt (P10.S1.T3, HANDOFF-01)

Revision ID: c8e4a1f7d263
Revises: b5d2e8a4c719
Create Date: 2026-10-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c8e4a1f7d263"
down_revision = "b5d2e8a4c719"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attempt", sa.Column("holder_session_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "attempt_holder_session_id_fkey", "attempt", "user_session", ["holder_session_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("attempt_holder_session_id_fkey", "attempt", type_="foreignkey")
    op.drop_column("attempt", "holder_session_id")
