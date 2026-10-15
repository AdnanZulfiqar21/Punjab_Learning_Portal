"""mistake_entry.flagged: the learner flagged the question as unsure (P12.S3.T1, NOTEBOOK-FLAGS-01)

One boolean column, false by default. The previous build neither reads nor writes it. Existing entries came from wrong
answers only, so false is correct for them; flagged questions from earlier tests are collected when the learner's
notebook is next replayed for those question families.

Revision ID: 5d7c1e7a1030
Revises: 5c86c03c84e3
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5d7c1e7a1030"
down_revision = "5c86c03c84e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mistake_entry", sa.Column("flagged", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column("mistake_entry", "flagged")
