from __future__ import annotations

import threading
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from portal_api.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_maker: sessionmaker[Session] | None = None
_lock = threading.Lock()


def _build_engine() -> Engine:
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


def get_engine() -> Engine:
    """One engine (one pool) per process. Built under a lock: `lru_cache` let concurrent first calls each create an
    engine with its own pool, exceeding the per-process connection budget on a cold start (review R08)."""
    global _engine
    engine = _engine
    if engine is not None:
        return engine
    with _lock:
        if _engine is None:
            _engine = _build_engine()
        return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _maker
    maker = _maker
    if maker is not None:
        return maker
    engine = get_engine()
    with _lock:
        if _maker is None:
            _maker = sessionmaker(bind=engine, expire_on_commit=False)
        return _maker


def reset_engine() -> None:
    """Tests only: dispose of the process engine so the next use builds a fresh one."""
    global _engine, _maker
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine, _maker = None, None


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one short-lived session per request (run in the bounded threadpool)."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
