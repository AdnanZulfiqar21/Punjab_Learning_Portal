"""audit trail is append-only (P16.S4.T1, AUDIT-01)

Revision ID: e8c1b7d4a206
Revises: d3f6a8b2c915
Create Date: 2026-10-09
"""

from __future__ import annotations

from alembic import op

revision = "e8c1b7d4a206"
down_revision = "d3f6a8b2c915"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create or replace function audit_event_append_only() returns trigger language plpgsql as $$
        begin
          raise exception 'audit_event is append-only (%)', tg_op using errcode = 'insufficient_privilege';
        end;
        $$;
        """
    )
    op.execute(
        "create trigger audit_event_no_change before update or delete on audit_event "
        "for each row execute function audit_event_append_only()"
    )


def downgrade() -> None:
    op.execute("drop trigger if exists audit_event_no_change on audit_event")
    op.execute("drop function if exists audit_event_append_only()")
