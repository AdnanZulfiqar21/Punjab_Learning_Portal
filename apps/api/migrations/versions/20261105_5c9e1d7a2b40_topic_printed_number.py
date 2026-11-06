"""The heading number a book prints for a topic, where the index records it (BOOK-NUMBER-02, MATHS-11-01).

Mathematics 11 Unit 1 prints "1.2" twice, "1.4" twice and "1.5" twice; students see 1.3, 1.6 and 1.7 and, beside
them, the book's own number ("Book# 1.2"), or "missing" where the book prints none. The natural keys of these topics
were made from their titles, so the printed number can't come from the key as it does for the others. A nullable
column; the previous build doesn't read it.

Revision ID: 5c9e1d7a2b40
Revises: 8d2f6b1e7a30
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5c9e1d7a2b40"
down_revision = "8d2f6b1e7a30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("topic", sa.Column("printed_number", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("topic", "printed_number")
