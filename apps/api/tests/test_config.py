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
    "evidence_s3_endpoint": "https://s3.internal.example",
    "evidence_s3_bucket": "portal-evidence",
    "evidence_s3_access_key": "deployed-access",
    "evidence_s3_secret_key": "deployed-secret-value",  # pragma: allowlist secret
    "trial_device_evidence": "fallback",
    "trial_ref_pepper": "deployment-secret-fixture",
    "notification_email_adapter": "none",  # P15.S1: the dev outbox is refused; "none" until a sender exists (B04)
    "upload_scanner": "clamd",  # P06.S4.T1: deployed roles scan uploads
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


def test_the_emulator_is_accepted_in_development_and_refused_when_deployed() -> None:
    emulator = {
        "evidence_store": "s3",
        "evidence_s3_endpoint": "http://127.0.0.1:59000",
        "evidence_s3_bucket": "portal-evidence-dev",
        "evidence_s3_access_key": "portal-dev-only",
        "evidence_s3_secret_key": "portal-dev-only",  # pragma: allowlist secret
    }
    assert Settings(role=Role.development, **emulator).evidence_s3_endpoint.endswith(":59000")
    base = {
        "role": Role.production,
        "database_url": PROD_DB,
        "public_api_origin": "https://api.example.org",
        "build_id": "sha-abc",
        "cors_origins": ["https://example.org"],
    }
    with pytest.raises(ConfigurationError, match="development endpoint or credential"):
        Settings(**{**OIDC, **emulator}, **base)
    with pytest.raises(ConfigurationError, match="endpoint, bucket"):
        Settings(**{**OIDC, "evidence_s3_endpoint": "", "evidence_s3_bucket": ""}, **base)


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_url": PROD_DB},
        {"public_api_origin": "https://api.sirfconcepts.example.org"},
        {"cors_origins": ["http://localhost:3100", "https://sirfconcepts.example.org"]},
        {"database_url": "postgresql+psycopg://app@52.95.110.1:5432/portal"},  # a public address (never contacted)
    ],
)
@pytest.mark.parametrize("role", [Role.development, Role.test])
def test_development_roles_refuse_a_real_deployments_addresses(role: Role, overrides: dict[str, object]) -> None:
    """ROLE-EXPLICIT-01: a server started without PORTAL_ROLE falls back to development, which mounts the code-free
    sign-in shortcuts and /docs. A non-local database or origin means the role was forgotten, so it refuses."""
    with pytest.raises(ConfigurationError, match="set PORTAL_ROLE"):
        Settings(role=role, **overrides)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"database_url": "postgresql+psycopg://portal@postgres:5432/portal"},  # a compose service name
        {"database_url": "postgresql+psycopg://portal@[::1]:5432/portal"},
        # a phone on the same Wi-Fi
        {"public_api_origin": "http://192.168.1.20:8100", "cors_origins": ["http://192.168.1.20:8190"]},
        {"public_api_origin": "http://api.portal.test:8100"},
        {"cors_origins": []},
    ],
)
def test_development_role_still_starts_on_a_laptop(overrides: dict[str, object]) -> None:
    assert Settings(role=Role.development, **overrides).role is Role.development  # type: ignore[arg-type]
