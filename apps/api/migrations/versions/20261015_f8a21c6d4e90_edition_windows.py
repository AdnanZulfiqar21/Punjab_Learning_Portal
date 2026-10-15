"""Edition windows on a textbook (P05.S1.T3).

effective_from is inclusive and effective_until is exclusive. Both stay null on the imported books, so they remain
effective on every day until a boundary is recorded. The previous build does not read the columns.

Revision ID: f8a21c6d4e90
Revises: cebd5a7f7015
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f8a21c6d4e90"
down_revision = "cebd5a7f7015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("book_edition", sa.Column("effective_from", sa.Date(), nullable=True))
    op.add_column("book_edition", sa.Column("effective_until", sa.Date(), nullable=True))
    op.create_check_constraint(
        "book_edition_window",
        "book_edition",
        "effective_until is null or effective_from is null or effective_until > effective_from",
    )


def downgrade() -> None:
    op.drop_constraint("book_edition_window", "book_edition", type_="check")
    op.drop_column("book_edition", "effective_until")
    op.drop_column("book_edition", "effective_from")
