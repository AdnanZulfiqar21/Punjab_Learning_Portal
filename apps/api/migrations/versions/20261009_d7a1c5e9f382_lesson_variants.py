"""content_item language, concept_id, translation_origin (P07.S1.T2, LESSON-VARIANTS-01)

Revision ID: d7a1c5e9f382
Revises: c4f8a2d9e517
Create Date: 2026-10-09

Existing items are English originals of their own concept (concept_id null).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d7a1c5e9f382"
down_revision = "c4f8a2d9e517"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_item", sa.Column("language", sa.String(length=10), server_default="en", nullable=False))
    op.add_column("content_item", sa.Column("concept_id", sa.UUID(), nullable=True))
    op.add_column("content_item", sa.Column("translation_origin", sa.String(length=14), nullable=True))
    op.create_index(op.f("ix_content_item_concept_id"), "content_item", ["concept_id"], unique=False)
    op.create_check_constraint("content_item_language", "content_item", "language in ('en','ur','roman_ur')")
    op.create_check_constraint(
        "content_item_translation_origin",
        "content_item",
        "translation_origin is null or translation_origin in ('human','machine_draft')",
    )


def downgrade() -> None:
    op.drop_constraint("content_item_translation_origin", "content_item", type_="check")
    op.drop_constraint("content_item_language", "content_item", type_="check")
    op.drop_index(op.f("ix_content_item_concept_id"), table_name="content_item")
    op.drop_column("content_item", "translation_origin")
    op.drop_column("content_item", "concept_id")
    op.drop_column("content_item", "language")
