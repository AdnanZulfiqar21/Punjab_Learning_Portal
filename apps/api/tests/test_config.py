"""Startup validator (P03.S2.T3): production refuses development adapters/URLs (roadmap §5.5)."""

from __future__ import annotations

import pytest

from portal_api.config import ConfigurationError, Role, Settings

PROD_DB = "postgresql+psycopg://app@db.internal.example:5432/portal"
OIDC = {
    "dev_auth_enabled": False,
    "oidc_issuer": "https://idp.example.org/pool",
    "oidc_audience": "client-1",
    "evidence_store": "s3",
    "trial_device_evidence": "fallback",
    "trial_ref_pepper": "deployment-secret-fixture",
}


def test_production_refuses_development_database_url() -> None:
    with pytest.raises(ConfigurationError, match="database_url"):
        Settings(
            **OIDC,
            role=Role.production,
            database_url="postgresql+psycopg://portal:portal-dev-only@127.0.0.1:55432/portal",
            public_api_origin="https://api.example.org",
            build_id="sha-abc",
            cors_origins=["https://example.org"],
        )


def test_production_requires_artifact_identity_and_no_dev_origins() -> None:
    with pytest.raises(ConfigurationError, match="build_id"):
        Settings(
            **OIDC,
            role=Role.production,
            database_url=PROD_DB,
            public_api_origin="https://api.example.org",
            cors_origins=["https://example.org"],
        )
    with pytest.raises(ConfigurationError, match="cors_origins"):
        Settings(
            **OIDC,
            role=Role.production,
            database_url=PROD_DB,
            public_api_origin="https://api.example.org",
            build_id="sha-abc",
            cors_origins=["http://localhost:3000"],
        )


def test_production_refuses_pool_overflow() -> None:
    with pytest.raises(ConfigurationError, match="max_overflow"):
        Settings(
            **OIDC,
            role=Role.production,
            database_url=PROD_DB,
            public_api_origin="https://api.example.org",
            build_id="sha-abc",
            cors_origins=["https://example.org"],
            db_max_overflow=5,
        )


def test_valid_production_and_staging_settings_start() -> None:
    Settings(
        **OIDC,
        role=Role.production,
        database_url=PROD_DB,
        public_api_origin="https://api.example.org",
        build_id="sha-abc",
        cors_origins=["https://example.org"],
    )
    Settings(
        **OIDC,
        role=Role.staging,
        database_url="postgresql+psycopg://app@staging-db.internal:5432/portal",
        public_api_origin="https://api.staging.example.org",
        build_id="sha-abc",
        cors_origins=["https://staging.example.org"],
    )


def test_production_refuses_the_development_identity_adapter() -> None:
    with pytest.raises(ConfigurationError, match="dev_auth_enabled"):
        Settings(
            role=Role.production,
            database_url=PROD_DB,
            public_api_origin="https://api.example.org",
            build_id="sha-abc",
            cors_origins=["https://example.org"],
            oidc_issuer="https://idp.example.org/pool",
            oidc_audience="client-1",
        )
    with pytest.raises(ConfigurationError, match="oidc_issuer"):
        Settings(
            role=Role.production,
            database_url=PROD_DB,
            public_api_origin="https://api.example.org",
            build_id="sha-abc",
            cors_origins=["https://example.org"],
            dev_auth_enabled=False,
        )


def test_production_refuses_the_local_evidence_directory() -> None:
    with pytest.raises(ConfigurationError, match="evidence_store"):
        Settings(
            **{**OIDC, "evidence_store": "local"},
            role=Role.production,
            database_url=PROD_DB,
            public_api_origin="https://api.example.org",
            build_id="sha-abc",
            cors_origins=["https://example.org"],
        )


def test_deployed_roles_must_choose_trial_evidence_and_a_pepper() -> None:
    base = {
        "role": Role.production,
        "database_url": PROD_DB,
        "public_api_origin": "https://api.example.org",
        "build_id": "sha-abc",
        "cors_origins": ["https://example.org"],
    }
    with pytest.raises(ConfigurationError, match="trial_device_evidence"):
        Settings(**{**OIDC, "trial_device_evidence": None}, **base)
    with pytest.raises(ConfigurationError, match="trial_ref_pepper"):
        Settings(**{**OIDC, "trial_ref_pepper": "dev-only-trial-pepper"}, **base)
    assert Settings(**OIDC, **base).trial_device_evidence == "fallback"  # an explicit, recorded choice is accepted
