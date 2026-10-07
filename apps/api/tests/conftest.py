"""Test fixtures: a disposable `portal_test` database, migrated from empty, loaded with the real catalogue.

Only the database named in PORTAL_TEST_DATABASE_URL is reset (P03.S4.T3: reset affects only the named disposable
environment). Negative tests use isolated malformed copies of the input files, never published content.
"""

from __future__ import annotations

import os
import tempfile

TEST_URL = os.environ.get(
    "PORTAL_TEST_DATABASE_URL", "postgresql+psycopg://portal:portal-dev-only@127.0.0.1:55432/portal_test"
)
assert TEST_URL.rsplit("/", 1)[-1].endswith("_test"), "refusing to run tests against a non-test database"
os.environ["PORTAL_DATABASE_URL"] = TEST_URL
os.environ["PORTAL_ROLE"] = "test"
# Uploaded evidence from tests goes to a throwaway directory, never the development store.
os.environ.setdefault("PORTAL_EVIDENCE_DIR", tempfile.mkdtemp(prefix="portal-evidence-test-"))

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from portal_api.db import get_sessionmaker  # noqa: E402
from portal_api.modules.curriculum.importer import DEFAULT_CATALOGUE, DEFAULT_REGISTRY, run_import  # noqa: E402

API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _reset_and_migrate() -> None:
    engine = create_engine(TEST_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    cfg = Config(os.path.join(API_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(API_DIR, "migrations"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def loaded_db() -> Iterator[None]:
    _reset_and_migrate()
    with get_sessionmaker()() as s:
        batch = run_import(s, DEFAULT_CATALOGUE, DEFAULT_REGISTRY, apply=True)
        assert batch.status == "APPLIED", batch.errors
    yield


@pytest.fixture
def db(loaded_db: None) -> Iterator[Session]:
    with get_sessionmaker()() as s:
        yield s


@pytest.fixture(scope="session")
def client(loaded_db: None) -> Iterator[TestClient]:
    from portal_api.main import create_app

    with TestClient(create_app()) as c:
        yield c
