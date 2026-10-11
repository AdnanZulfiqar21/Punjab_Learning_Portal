"""concept, concept_topic, concept_prerequisite: learning concepts and prerequisites (P05.S1.T2, CONCEPTS-01)

Revision ID: e3b9f1c7a426
Revises: d7a2c5e9f318
Create Date: 2026-10-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e3b9f1c7a426"
down_revision = "d7a2c5e9f318"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "concept",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("subject_code", sa.String(length=40), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("published_by", sa.UUID(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status in ('draft', 'published', 'retired')", name="concept_status"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_concept_subject_code"), "concept", ["subject_code"], unique=False)
    op.create_table(
        "concept_topic",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("concept_id", sa.UUID(), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["concept_id"], ["concept.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topic.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concept_id", "topic_id", name="uq_concept_topic"),
    )
    op.create_index(op.f("ix_concept_topic_concept_id"), "concept_topic", ["concept_id"], unique=False)
    op.create_index(op.f("ix_concept_topic_topic_id"), "concept_topic", ["topic_id"], unique=False)
    op.create_table(
        "concept_prerequisite",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("concept_id", sa.UUID(), nullable=False),
        sa.Column("requires_id", sa.UUID(), nullable=False),
        sa.Column("bridging_lesson_id", sa.UUID(), nullable=True),
        sa.CheckConstraint("concept_id <> requires_id", name="concept_prerequisite_not_self"),
        sa.ForeignKeyConstraint(["bridging_lesson_id"], ["content_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["concept_id"], ["concept.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requires_id"], ["concept.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concept_id", "requires_id", name="uq_concept_prerequisite"),
    )
    op.create_index(op.f("ix_concept_prerequisite_concept_id"), "concept_prerequisite", ["concept_id"], unique=False)
    op.create_index(op.f("ix_concept_prerequisite_requires_id"), "concept_prerequisite", ["requires_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_concept_prerequisite_requires_id"), table_name="concept_prerequisite")
    op.drop_index(op.f("ix_concept_prerequisite_concept_id"), table_name="concept_prerequisite")
    op.drop_table("concept_prerequisite")
    op.drop_index(op.f("ix_concept_topic_topic_id"), table_name="concept_topic")
    op.drop_index(op.f("ix_concept_topic_concept_id"), table_name="concept_topic")
    op.drop_table("concept_topic")
    op.drop_index(op.f("ix_concept_subject_code"), table_name="concept")
    op.drop_table("concept")
