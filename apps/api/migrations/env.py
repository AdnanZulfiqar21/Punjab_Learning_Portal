"""Alembic environment. Migrations run once per release as a separate step, never on container startup (§5.3)."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool

import portal_api.modules.access.models
import portal_api.modules.access.trial_devices
import portal_api.modules.assessment.models
import portal_api.modules.audit.models
import portal_api.modules.content.models
import portal_api.modules.curriculum.models
import portal_api.modules.help.models
import portal_api.modules.identity.models
import portal_api.modules.identity.sessions
import portal_api.modules.notifications.models
import portal_api.modules.support.models
import portal_api.modules.written.adjudication
import portal_api.modules.written.models
import portal_api.modules.written.regrade_jobs
import portal_api.modules.written.rescans
import portal_api.modules.written.review  # noqa: F401
from portal_api.config import get_settings
from portal_api.db import Base

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
