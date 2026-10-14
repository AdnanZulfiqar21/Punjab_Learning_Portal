"""content_import_batch.attempts and last_error: bounded retries for the import worker (OCT14-03)

Two columns: attempts (not null, server default 0, so the previous build's inserts still work) and last_error
(nullable, operators only). The previous build neither reads nor writes them.

Revision ID: 1311c92533d7
Revises: 8d67f124450b
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "1311c92533d7"
down_revision = "8d67f124450b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_import_batch", sa.Column("attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("content_import_batch", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("content_import_batch", "last_error")
    op.drop_column("content_import_batch", "attempts")
