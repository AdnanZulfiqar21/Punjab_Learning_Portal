"""help centre articles and service incidents (P15.S2)

Revision ID: 7f3e2a91c4d6
Revises: 20ca22d182aa
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "7f3e2a91c4d6"
down_revision = "20ca22d182aa"
branch_labels = None
depends_on = None

J = postgresql.JSONB(astext_type=sa.Text())
NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "help_article",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("locale", sa.String(length=2), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("working_version_id", sa.UUID(), nullable=True),
        sa.Column("published_version_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.CheckConstraint("locale in ('en','ur')", name="help_article_locale"),
        sa.CheckConstraint("status in ('draft','published','retired')", name="help_article_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", "locale", name="uq_help_article_slug_locale"),
    )
    op.create_table(
        "help_article_version",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=400), nullable=False),
        sa.Column("body", J, nullable=False),
        sa.Column("tags", J, nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["help_article.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "number", name="uq_help_version_number"),
    )
    op.create_index(op.f("ix_help_article_version_article_id"), "help_article_version", ["article_id"], unique=False)
    op.create_foreign_key(
        "fk_help_working", "help_article", "help_article_version", ["working_version_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "fk_help_published",
        "help_article",
        "help_article_version",
        ["published_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "service_incident",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=14), nullable=False),
        sa.Column("components", J, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "status in ('investigating','identified','monitoring','resolved')", name="service_incident_status"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "service_incident_update",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("incident_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=14), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("by", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["incident_id"], ["service_incident.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_service_incident_update_incident_id"), "service_incident_update", ["incident_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_service_incident_update_incident_id"), table_name="service_incident_update")
    op.drop_table("service_incident_update")
    op.drop_table("service_incident")
    op.drop_constraint("fk_help_published", "help_article", type_="foreignkey")
    op.drop_constraint("fk_help_working", "help_article", type_="foreignkey")
    op.drop_index(op.f("ix_help_article_version_article_id"), table_name="help_article_version")
    op.drop_table("help_article_version")
    op.drop_table("help_article")
