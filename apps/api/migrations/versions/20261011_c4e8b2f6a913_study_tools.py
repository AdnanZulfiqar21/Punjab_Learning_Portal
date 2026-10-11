"""study tools: private lesson notes, topic favourites, saved formulas (P11.S2.T2, STUDY-TOOLS-01)

Revision ID: c4e8b2f6a913
Revises: a7c3e9d1f264
Create Date: 2026-10-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c4e8b2f6a913"
down_revision = "a7c3e9d1f264"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_favourite",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["topic_id"], ["topic.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "topic_id", name="uq_topic_favourite"),
    )
    op.create_index(op.f("ix_topic_favourite_user_id"), "topic_favourite", ["user_id"], unique=False)
    op.create_table(
        "study_note",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["content_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "item_id", name="uq_study_note_lesson"),
    )
    op.create_index(op.f("ix_study_note_user_id"), "study_note", ["user_id"], unique=False)
    op.create_table(
        "saved_formula",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("block_index", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["content_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["version_id"], ["content_version.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "version_id", "block_index", name="uq_saved_formula_block"),
    )
    op.create_index(op.f("ix_saved_formula_user_id"), "saved_formula", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_saved_formula_user_id"), table_name="saved_formula")
    op.drop_table("saved_formula")
    op.drop_index(op.f("ix_study_note_user_id"), table_name="study_note")
    op.drop_table("study_note")
    op.drop_index(op.f("ix_topic_favourite_user_id"), table_name="topic_favourite")
    op.drop_table("topic_favourite")
