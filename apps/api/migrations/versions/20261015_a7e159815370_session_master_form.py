"""mock_session.master_form_id: the session's fixed comparable form (P09.S3.T3, FIXED-FORMS-01)

One nullable column referencing practice_form. The previous build neither reads nor writes it; sessions already
running keep building one form per participant until their next join after the upgrade sets a master.

Revision ID: a7e159815370
Revises: dae236340bd6
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7e159815370"
down_revision = "dae236340bd6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mock_session",
        sa.Column(
            "master_form_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("practice_form.id", ondelete="RESTRICT", name="fk_mock_session_master_form"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_constraint("fk_mock_session_master_form", "mock_session", type_="foreignkey")
    op.drop_column("mock_session", "master_form_id")
