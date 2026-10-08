"""lesson access tier (review R07)

Every existing item becomes premium: nothing is free unless a publisher explicitly marks a preview (ACCESS-02).

Revision ID: c7a1e2f4b9d0
Revises: 648941e093b0
Create Date: 2026-10-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7a1e2f4b9d0"
down_revision: str | Sequence[str] | None = "648941e093b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "content_item", sa.Column("access_tier", sa.String(length=10), server_default="premium", nullable=False)
    )
    op.create_check_constraint("content_item_access_tier", "content_item", "access_tier in ('preview','premium')")


def downgrade() -> None:
    op.drop_constraint("content_item_access_tier", "content_item", type_="check")
    op.drop_column("content_item", "access_tier")
