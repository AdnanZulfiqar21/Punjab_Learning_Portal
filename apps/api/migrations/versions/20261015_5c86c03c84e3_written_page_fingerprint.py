"""written_page.fingerprint: a coarse page thumbnail for flagging the same page uploaded twice (W03.S2.T3, NEAR-DUP-01)

One nullable column. The previous build neither reads nor writes it; pages uploaded before it stay unflagged.

Revision ID: 5c86c03c84e3
Revises: f2ce265b3089
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5c86c03c84e3"
down_revision = "f2ce265b3089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("written_page", sa.Column("fingerprint", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("written_page", "fingerprint")
