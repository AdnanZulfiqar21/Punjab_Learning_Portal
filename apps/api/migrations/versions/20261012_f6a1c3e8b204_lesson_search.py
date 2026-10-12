"""lesson_search_text(), the lesson full-text index, search_alias_group, search_alias: content search (P11.S2.T3,
SEARCH-01)

`lesson_search_text(body)` is the one definition of which lesson text is searchable and quotable in a snippet:
headings, paragraphs, lists, callouts, tables, equation text alternatives, worked-example titles, problems and steps,
diagram captions and descriptions, handout titles. Checkpoints (their prompts, options, keys and explanations) and
worked-example answers are left out so a snippet never gives an answer away. It never raises: a malformed draft body
indexes as empty text instead of blocking the save. Urdu text is normalised the same way as search queries
(`content.search.normalise`): Arabic yeh and kaf to their Urdu forms, diacritics, tatweel and joiners removed.

Revision ID: f6a1c3e8b204
Revises: e4b8d2c7f913
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6a1c3e8b204"
down_revision = "e4b8d2c7f913"
branch_labels = None
depends_on = None

# Keep in step with content.search.FOLD and content.search.DROP.
FOLD_FROM = r"يىك"
FOLD_TO = r"ییک"
DROP = (
    r"ًٌٍَُِّْٕٖٜٓٔٗ٘ٙٚٛ"
    r"ٰٟٝٞـ‌‍\u0002\u0003"
)

LESSON_SEARCH_TEXT = f"""
CREATE FUNCTION lesson_search_text(body jsonb) RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $fn$
BEGIN
  RETURN translate(normalize(coalesce((
    SELECT string_agg(part, ' ' ORDER BY i, j)
      FROM jsonb_array_elements(
             CASE WHEN jsonb_typeof(body -> 'blocks') = 'array' THEN body -> 'blocks' ELSE '[]'::jsonb END
           ) WITH ORDINALITY AS b(blk, i),
           LATERAL jsonb_array_elements_text(
             CASE WHEN jsonb_typeof(blk) <> 'object' THEN '[]'::jsonb ELSE CASE blk ->> 'type'
               WHEN 'heading' THEN jsonb_build_array(blk -> 'text')
               WHEN 'paragraph' THEN jsonb_build_array(blk -> 'text')
               WHEN 'list' THEN jsonb_path_query_array(blk, 'lax $.items[*]')
               WHEN 'callout' THEN jsonb_build_array(blk -> 'title', blk -> 'text')
               WHEN 'table' THEN jsonb_build_array(blk -> 'caption')
                 || jsonb_path_query_array(blk, 'lax $.header[*]') || jsonb_path_query_array(blk, 'lax $.rows[*][*]')
               WHEN 'equation' THEN jsonb_build_array(blk -> 'text_alt')
               WHEN 'example' THEN jsonb_build_array(blk -> 'title', blk -> 'problem')
                 || jsonb_path_query_array(blk, 'lax $.steps[*]')
               WHEN 'diagram' THEN jsonb_build_array(blk -> 'caption', blk -> 'alt', blk -> 'long_description')
               WHEN 'handout' THEN jsonb_build_array(blk -> 'title', blk -> 'description')
               ELSE '[]'::jsonb END END
           ) WITH ORDINALITY AS x(part, j)
  ), ''), NFKC), E'{FOLD_FROM}{DROP}', E'{FOLD_TO}');
EXCEPTION WHEN others THEN
  RETURN '';
END
$fn$
"""  # noqa: S608 (constants only, no input)


def upgrade() -> None:
    op.execute(LESSON_SEARCH_TEXT)
    op.execute(
        "CREATE INDEX ix_content_version_search ON content_version "
        "USING gin (to_tsvector('english'::regconfig, lesson_search_text(body)))"
    )
    op.create_table(
        "search_alias_group",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("grade_number", sa.SmallInteger(), nullable=False),
        sa.Column("subject_code", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("source_ref", sa.String(length=300), nullable=False),
        sa.Column("proposed_by", sa.UUID(), nullable=False),
        sa.Column("proposed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_by", sa.UUID(), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_reason", sa.String(length=300), nullable=True),
        sa.CheckConstraint("grade_number in (11, 12)", name="search_alias_group_grade"),
        sa.CheckConstraint("status in ('proposed','approved','retired')", name="search_alias_group_status"),
        sa.CheckConstraint("approved_by is null or approved_by <> proposed_by", name="search_alias_group_independent"),
        sa.CheckConstraint(
            "status <> 'approved' or approved_by is not null", name="search_alias_group_approved_has_approver"
        ),
        sa.ForeignKeyConstraint(["approved_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["proposed_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["retired_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_search_alias_group_scope", "search_alias_group", ["grade_number", "subject_code", "status"], unique=False
    )
    op.create_table(
        "search_alias",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("text", sa.String(length=80), nullable=False),
        sa.Column("normalized", sa.String(length=80), nullable=False),
        sa.CheckConstraint("language in ('en','ur','roman_ur')", name="search_alias_language"),
        sa.ForeignKeyConstraint(["group_id"], ["search_alias_group.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "normalized", name="uq_search_alias_form"),
    )
    op.create_index("ix_search_alias_normalized", "search_alias", ["normalized"], unique=False)
    op.create_index(
        "ix_search_alias_normalized_trgm",
        "search_alias",
        ["normalized"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"normalized": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_search_alias_normalized_trgm", table_name="search_alias")
    op.drop_index("ix_search_alias_normalized", table_name="search_alias")
    op.drop_table("search_alias")
    op.drop_index("ix_search_alias_group_scope", table_name="search_alias_group")
    op.drop_table("search_alias_group")
    op.execute("DROP INDEX ix_content_version_search")
    op.execute("DROP FUNCTION lesson_search_text(jsonb)")
