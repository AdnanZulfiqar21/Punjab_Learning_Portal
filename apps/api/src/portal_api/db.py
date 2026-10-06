from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from portal_api.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    s = get_settings()
    engine = create_engine(
        s.database_url,
        pool_size=s.db_pool_size,
        max_overflow=s.db_max_overflow,
        pool_pre_ping=True,
        pool_timeout=5,
    )

    @event.listens_for(engine, "connect")
    def _set_timeouts(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        with dbapi_conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {int(s.db_statement_timeout_ms)}")
        dbapi_conn.commit()

    return engine


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one short-lived session per request (run in the bounded threadpool)."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
