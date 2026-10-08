"""trial claims, device uses and exceptions (review R06; roadmap §16.4)

Revision ID: d4f8a1c3e2b7
Revises: b1e32702b01c
Create Date: 2026-10-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4f8a1c3e2b7"
down_revision: str | Sequence[str] | None = "b1e32702b01c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATES = (
    "PENDING_VERIFICATION",
    "MARK_PENDING",
    "MARK_UNKNOWN",
    "MARK_CONFIRMED",
    "GRANTED",
    "REVIEW_REQUIRED",
    "CLOSED_INELIGIBLE",
)


def upgrade() -> None:
    op.create_table(
        "trial_claim",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("program", sa.String(length=40), nullable=False),
        sa.Column("offer_terms_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("surface", sa.String(length=10), nullable=False),
        sa.Column("installation_ref", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("grant_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"status in ({', '.join(repr(s) for s in STATES)})", name="trial_claim_status"),
        sa.CheckConstraint("surface in ('web','ios','android')", name="trial_claim_surface"),
        sa.ForeignKeyConstraint(["grant_id"], ["trial_grant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_trial_claim_key"),
    )
    op.create_index(op.f("ix_trial_claim_user_id"), "trial_claim", ["user_id"], unique=False)
    op.create_table(
        "trial_claim_event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["trial_claim.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trial_claim_event_claim_id"), "trial_claim_event", ["claim_id"], unique=False)
    op.create_table(
        "trial_device_use",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("grant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("surface", sa.String(length=10), nullable=False),
        sa.Column("installation_ref", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("replaces_id", sa.UUID(), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('authorized','removed')", name="trial_device_use_status"),
        sa.CheckConstraint(
            "method in ('first_use','recovery','exception','fallback','web')", name="trial_device_use_method"
        ),
        sa.ForeignKeyConstraint(["grant_id"], ["trial_grant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["replaces_id"], ["trial_device_use.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trial_device_use_grant_id"), "trial_device_use", ["grant_id"], unique=False)
    op.create_index(op.f("ix_trial_device_use_user_id"), "trial_device_use", ["user_id"], unique=False)
    op.create_table(
        "trial_exception",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("surface", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("granted_by", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["granted_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trial_exception_user_id"), "trial_exception", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_trial_exception_user_id"), table_name="trial_exception")
    op.drop_table("trial_exception")
    op.drop_index(op.f("ix_trial_device_use_user_id"), table_name="trial_device_use")
    op.drop_index(op.f("ix_trial_device_use_grant_id"), table_name="trial_device_use")
    op.drop_table("trial_device_use")
    op.drop_index(op.f("ix_trial_claim_event_claim_id"), table_name="trial_claim_event")
    op.drop_table("trial_claim_event")
    op.drop_index(op.f("ix_trial_claim_user_id"), table_name="trial_claim")
    op.drop_table("trial_claim")
