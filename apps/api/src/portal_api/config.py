"""Runtime configuration and the startup validator (P03.S2.T3, roadmap §5.5).

Every environment-specific value comes from the environment at runtime. The validator refuses to start a
production role with development/staging adapters, URLs or credentials, so a promoted image can never
silently carry them.
"""

from __future__ import annotations

import ipaddress
from enum import StrEnum
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Role(StrEnum):
    development = "development"
    test = "test"
    staging = "staging"
    production = "production"


class ConfigurationError(RuntimeError):
    """Raised at startup when settings are missing or conflict."""


# The issuer of development/test accounts (the local password issuer outside deployed roles).
DEV_ISSUER = "urn:portal:dev-local-issuer"
DEV_MARKERS = ("localhost", "127.0.0.1", "dev-only", "portal-dev", "sandbox", "staging")


def _is_local_host(host: str | None) -> bool:
    """A host on this machine or a private network: a developer's laptop, a phone on the same Wi-Fi, a compose
    service name. Any other name or a public address belongs to a real deployment."""
    if not host:
        return True
    name = host.strip("[]").lower()
    try:
        ip = ipaddress.ip_address(name)
    except ValueError:
        return "." not in name or name == "host.docker.internal" or name.endswith((".localhost", ".local", ".test"))
    return ip.is_loopback or ip.is_private or ip.is_link_local


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PORTAL_", env_file=None, extra="ignore")

    role: Role = Role.development
    database_url: str = Field(default="postgresql+psycopg://portal:portal-dev-only@127.0.0.1:55432/portal")
    # Public, non-secret values delivered to web/mobile at runtime (never baked into builds).
    public_api_origin: str = "http://127.0.0.1:8100"
    public_media_origin: str = ""
    build_id: str = "local"
    cors_origins: list[str] = Field(
        # Development defaults: web app (3100) and the Expo web target (8190). Deployed roles must set their own.
        default_factory=lambda: ["http://localhost:3100", "http://127.0.0.1:3100", "http://localhost:8190"]
    )
    # LECTURE-READ-01: development/test only. A directory holding registered master videos so the pilot can stream a
    # lecture on the local network. Deployed roles must use the media provider (B05) and refuse this setting.
    lecture_media_dir: str = ""
    # P05.S4.T2 (REGION-01): regions learners can discover. Another region's records stay hidden until the owner
    # authorises its release by adding it here.
    released_regions: list[str] = Field(default_factory=lambda: ["pk-punjab"])
    db_pool_size: int = 10  # per-process pool; multiplied by process count in the §5.8 budget
    db_max_overflow: int = 0
    # P17.S2.T2 (POOL-CAPS-01): bulk-class commands claim no new work around scheduled mock windows.
    bulk_pause_in_mock_windows: bool = True
    # W09.S1.T3 (WORKLOAD-GUARD-01): each API process publishes its MCQ save health this often (seconds); 0 = off.
    health_sample_s: float = 20.0
    db_statement_timeout_ms: int = 5000
    # READING-PLACE-CACHE-01: seconds a process keeps a topic's catalogue place and neighbours (0 = off).
    reading_place_cache_s: float = Field(default=60.0, ge=0)
    # ADMISSION-01: requests admitted at once per API process (0 = twice the pool) and how long one may wait for a slot
    # before a 503 SERVICE_BUSY. The worker-thread pool is kept at least twice the slots.
    api_admission_slots: int = Field(default=0, ge=0)
    api_admission_wait_s: float = Field(default=5.0, gt=0)

    # Identity (P04). AUTH-PASSWORD-01 (owner 2026-11-11): the portal's own email + password sign-up, with the email
    # proved by a 6-digit code (sent through the email adapter, Resend in deployed roles), is the production sign-in.
    # Its issuer signs short-lived access tokens with `password_auth_signing_key` (an RSA private key, PEM; a deployment
    # secret). Without a key (development/test only) the key is generated per process. An external OIDC issuer may be
    # trusted as well (or instead, with password_auth_enabled=false).
    password_auth_enabled: bool = True
    password_auth_issuer: str = DEV_ISSUER
    password_auth_audience: str = "portal-api"  # noqa: S105 (a token audience, not a password)
    password_auth_token_ttl_s: int = 900
    password_auth_signing_key: SecretStr = SecretStr("")
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None  # defaults to <issuer>/.well-known/jwks.json
    # Development/test-only shortcuts on the same issuer: registration without an email code and a simulated MFA claim.
    # Refused in staging/production by the validator.
    dev_auth_enabled: bool = True

    # Handwritten-answer evidence and lesson assets (W03, P03.S1.T2). "local" is a private directory for
    # development/test only. "s3" is the path-style client: the compose emulator in development, or a private bucket
    # once the owner chooses an account and region (B03, D14). The region string is only for request signing.
    evidence_store: Literal["local", "s3"] = "local"
    evidence_dir: str = "var/evidence"
    evidence_s3_endpoint: str = ""
    evidence_s3_bucket: str = ""
    evidence_s3_access_key: str = ""
    evidence_s3_secret_key: str = ""
    evidence_s3_region: str = "us-east-1"
    # Upload scanning (P06.S4.T1). "clamd" scans every learner upload before storage; "none" is development/test only.
    upload_scanner: Literal["none", "clamd"] = "none"
    clamd_host: str = "127.0.0.1"
    clamd_port: int = 3310
    # Daily usage budgets for paid providers (P16.S3.T2): the operator view warns at 80% and alerts at 100%. Unset = no
    # budget recorded yet (set them when the providers and prices are chosen: B04, B10).
    email_daily_budget: int | None = None
    assessor_daily_budget: int | None = None

    # Trial device evidence (roadmap §16, review R06). "required": unknown native evidence never completes a claim.
    # "fallback": while a device provider is unconfigured (B07/B08), native activation uses account history alone and
    # records that it did. Deployed roles must choose explicitly. The pepper salts opaque installation references.
    trial_device_evidence: Literal["required", "fallback"] | None = None
    trial_ref_pepper: str = "dev-only-trial-pepper"

    # Notifications (P15.S1). "dev_outbox" records rendered email locally (development/test only); "none" leaves email
    # deliveries visibly unavailable until an approved sender exists (BLOCKERS B04). Push has no provider until B07.
    # "resend" sends through Resend's HTTPS API (AUTH-PASSWORD-01) with `resend_api_key` (a deployment secret) from
    # `email_from`, an address on a domain verified in Resend (e.g. "Sirf Concepts <no-reply@sirfconcepts.com>").
    notification_email_adapter: Literal["dev_outbox", "none", "resend"] = "dev_outbox"
    resend_api_key: SecretStr = SecretStr("")
    resend_api_url: str = "https://api.resend.com/emails"
    email_from: str = ""
    # Automatic written assessment (W05). "none" until a qualified provider is approved (BLOCKERS B10); "fixture" is a
    # deterministic technical fixture for development/test only.
    written_assessor: Literal["none", "fixture"] = "none"
    # W06.S1.T3 (CALIBRATION-01): the share of sealed scripts in the evaluation subset whose blinded teacher marks are
    # compared with automatic proposals (evidence for the WG10 gate; nothing is ever published from it).
    written_evaluation_percent: int = Field(default=100, ge=0, le=100)
    # W08.S1.T1 (PILOT-R0-01): the written release level (roadmap §20.15). "r0_pilot" offers written practice only
    # to learners with an active pilot entitlement, whose units fund it (tracked, non-billable; every mark is a
    # teacher's). "open" lets any plan's marking units fund it. Unset means r0_pilot in deployed roles, because no
    # later level is qualified yet (WA-D12, B10), and open in development and test.
    written_release: Literal["r0_pilot", "open"] | None = None

    @model_validator(mode="after")
    def _validate_role(self) -> Settings:
        if self.role in (Role.production, Role.staging):
            problems = []
            for name in ("database_url", "public_api_origin"):
                value = str(getattr(self, name)).lower()
                bad = [m for m in DEV_MARKERS if m in value and not (self.role is Role.staging and m == "staging")]
                if bad:
                    problems.append(f"{name} contains development marker(s) {bad}")
            if self.role is Role.production and any(m in o.lower() for o in self.cors_origins for m in DEV_MARKERS):
                problems.append("cors_origins contains development/staging origins")
            if self.build_id == "local":
                problems.append("build_id must identify the immutable artifact")
            if self.lecture_media_dir:
                problems.append(
                    "lecture_media_dir is a development streaming path; deployed roles use the media provider"
                )
            if self.dev_auth_enabled:
                problems.append("dev_auth_enabled must be false (development identity adapter)")
            if self.password_auth_enabled:
                if not self.password_auth_signing_key.get_secret_value().strip():
                    problems.append("password_auth_signing_key is required (RSA private key, PEM)")
                issuer = self.password_auth_issuer.lower()
                if "dev-local" in issuer or any(m in issuer for m in DEV_MARKERS if m != "staging"):
                    problems.append("password_auth_issuer is a development issuer")
                if self.notification_email_adapter != "resend":
                    problems.append("password_auth_enabled needs an email sender (notification_email_adapter=resend)")
            elif not (self.oidc_issuer and self.oidc_audience):
                problems.append("oidc_issuer and oidc_audience are required when password_auth_enabled is false")
            if self.oidc_issuer and (
                any(m in self.oidc_issuer.lower() for m in DEV_MARKERS if m != "staging")
                or "dev-local" in self.oidc_issuer
            ):
                problems.append("oidc_issuer points at a development issuer")
            if self.evidence_store == "local":
                problems.append("evidence_store must be private object storage, not the local development directory")
            elif not all(
                (
                    self.evidence_s3_endpoint,
                    self.evidence_s3_bucket,
                    self.evidence_s3_access_key,
                    self.evidence_s3_secret_key,
                )
            ):
                problems.append("evidence_store=s3 needs an endpoint, bucket, access key and secret key")
            else:
                blob = " ".join(
                    (
                        self.evidence_s3_endpoint,
                        self.evidence_s3_bucket,
                        self.evidence_s3_access_key,
                        self.evidence_s3_secret_key,
                    )
                ).lower()
                markers = [m for m in DEV_MARKERS if m in blob and not (self.role is Role.staging and m == "staging")]
                if markers or "minioadmin" in blob:
                    problems.append(
                        "evidence object storage uses a development endpoint or credential "
                        + str(markers or ["minioadmin"])
                    )
            if self.trial_device_evidence is None:
                problems.append("trial_device_evidence must be set explicitly (required or fallback; roadmap §16)")
            if self.notification_email_adapter == "dev_outbox":
                problems.append("notification_email_adapter dev_outbox is development/test only")
            if self.notification_email_adapter == "resend":
                if not self.resend_api_key.get_secret_value().strip():
                    problems.append("notification_email_adapter=resend needs resend_api_key")
                if "@" not in self.email_from:
                    problems.append("notification_email_adapter=resend needs email_from")
                elif self.role is Role.production and "resend.dev" in self.email_from.lower():
                    # Resend's shared test address only delivers to the Resend account's own inbox.
                    problems.append("email_from must be on the portal's own verified domain, not resend.dev")
            if self.upload_scanner == "none":
                problems.append("upload_scanner must scan uploads (clamd) in deployed roles")
            if self.written_assessor == "fixture":
                problems.append("written_assessor fixture is development/test only")
            if self.trial_ref_pepper.startswith("dev-only"):
                problems.append("trial_ref_pepper must be a deployment secret")
            if problems:
                raise ConfigurationError(f"refusing to start role={self.role.value}: " + "; ".join(problems))
        elif self.notification_email_adapter == "resend" and not (
            self.resend_api_key.get_secret_value().strip() and "@" in self.email_from
        ):
            raise ConfigurationError("notification_email_adapter=resend needs resend_api_key and email_from")
        elif self.evidence_store == "s3" and not all(
            (
                self.evidence_s3_endpoint,
                self.evidence_s3_bucket,
                self.evidence_s3_access_key,
                self.evidence_s3_secret_key,
            )
        ):
            raise ConfigurationError("evidence_store=s3 needs an endpoint, bucket, access key and secret key")
        if self.db_max_overflow != 0 and self.role is Role.production:
            raise ConfigurationError("db_max_overflow must be 0 in production (connection budget, roadmap §5.8)")
        return self

    @model_validator(mode="after")
    def _validate_role_is_deliberate(self) -> Settings:
        """ROLE-EXPLICIT-01 (security audit 2026-11, H1): `development` is the default so a laptop needs no setup, and
        it mounts the code-free sign-in shortcuts, a simulated second factor and /docs. A server started without
        PORTAL_ROLE would therefore be wide open without any error. So the development and test roles refuse any
        address that is not on this machine or a private network: a real database or a public origin means the role
        was forgotten."""
        if self.role in (Role.production, Role.staging):
            return self
        remote = []
        checked = (
            ("database_url", [self.database_url]),
            ("public_api_origin", [self.public_api_origin]),
            ("cors_origins", self.cors_origins),
        )
        for name, values in checked:
            for value in values:
                try:
                    host = urlsplit(value).hostname
                except ValueError:
                    host = None
                if not _is_local_host(host):
                    remote.append(name)
                    break
        if remote:
            raise ConfigurationError(
                f"refusing to start role={self.role.value} with a non-local {', '.join(remote)}: set PORTAL_ROLE to "
                "production or staging on a server (the development role opens sign-in shortcuts and /docs)"
            )
        return self

    @property
    def written_pilot_only(self) -> bool:
        if self.written_release is not None:
            return self.written_release == "r0_pilot"
        return self.role in (Role.production, Role.staging)

    @property
    def test_account_issuer(self) -> str:
        """Accounts from this issuer are development/test accounts, kept out of learner analytics and cohorts. In
        development/test every local account is one; in deployed roles real learners sign up with the password issuer,
        so only the development issuer (never trusted there) counts."""
        if self.role in (Role.production, Role.staging):
            return DEV_ISSUER
        return self.password_auth_issuer

    @property
    def jwks_url(self) -> str | None:
        if self.oidc_jwks_url:
            return self.oidc_jwks_url
        return f"{self.oidc_issuer.rstrip('/')}/.well-known/jwks.json" if self.oidc_issuer else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
