"""Startup validator (P03.S2.T3): production refuses development adapters/URLs (roadmap §5.5)."""

from __future__ import annotations

import pytest

from portal_api.config import ConfigurationError, Role, Settings

PROD_DB = "postgresql+psycopg://app@db.internal.example:5432/portal"


def test_production_refuses_development_database_url() -> None:
    with pytest.raises(ConfigurationError, match="database_url"):
        Settings(
            role=Role.production,
            database_url="postgresql+psycopg://portal:portal-dev-only@127.0.0.1:55432/portal",
            public_api_origin="https://api.example.org",
            build_id="sha-abc",
            cors_origins=["https://example.org"],
        )


def test_production_requires_artifact_identity_and_no_dev_origins() -> None:
    with pytest.raises(ConfigurationError, match="build_id"):
        Settings(
            role=Role.production,
            database_url=PROD_DB,
            public_api_origin="https://api.example.org",
            cors_origins=["https://example.org"],
        )
    with pytest.raises(ConfigurationError, match="cors_origins"):
        Settings(
            role=Role.production,
            database_url=PROD_DB,
            public_api_origin="https://api.example.org",
            build_id="sha-abc",
            cors_origins=["http://localhost:3000"],
        )


def test_production_refuses_pool_overflow() -> None:
    with pytest.raises(ConfigurationError, match="max_overflow"):
        Settings(
            role=Role.production,
            database_url=PROD_DB,
            public_api_origin="https://api.example.org",
            build_id="sha-abc",
            cors_origins=["https://example.org"],
            db_max_overflow=5,
        )


def test_valid_production_and_staging_settings_start() -> None:
    Settings(
        role=Role.production,
        database_url=PROD_DB,
        public_api_origin="https://api.example.org",
        build_id="sha-abc",
        cors_origins=["https://example.org"],
    )
    Settings(
        role=Role.staging,
        database_url="postgresql+psycopg://app@staging-db.internal:5432/portal",
        public_api_origin="https://api.staging.example.org",
        build_id="sha-abc",
        cors_origins=["https://staging.example.org"],
    )
