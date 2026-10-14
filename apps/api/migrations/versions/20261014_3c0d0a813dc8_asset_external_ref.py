"""content_asset.external_ref: the media pack key (P06.S2.T1, MEDIA-MANIFEST-01)

One nullable column and a partial unique index (class, subject, key). The previous build neither reads nor writes
the column, and its inserts leave it null, so it runs unchanged on this schema.

Revision ID: 3c0d0a813dc8
Revises: 219df9c8c75c
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "3c0d0a813dc8"
down_revision = "219df9c8c75c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_asset", sa.Column("external_ref", sa.String(length=120), nullable=True))
    op.create_index(
        "uq_content_asset_external_ref",
        "content_asset",
        ["grade_number", "subject_code", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref is not null"),
    )


def downgrade() -> None:
    op.drop_index("uq_content_asset_external_ref", table_name="content_asset")
    op.drop_column("content_asset", "external_ref")
