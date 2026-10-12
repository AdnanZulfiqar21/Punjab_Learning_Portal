"""Runtime configuration and the startup validator (P03.S2.T3, roadmap §5.5).

Every environment-specific value comes from the environment at runtime. The validator refuses to start a
production role with development/staging adapters, URLs or credentials, so a promoted image can never
silently carry them.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Role(StrEnum):
    development = "development"
    test = "test"
    staging = "staging"
    production = "production"


class ConfigurationError(RuntimeError):
    """Raised at startup when settings are missing or conflict."""


DEV_MARKERS = ("localhost", "127.0.0.1", "dev-only", "portal-dev", "sandbox", "staging")


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
    # P05.S4.T2 (REGION-01): regions learners can discover. Another region's records stay hidden until the owner
    # authorises its release by adding it here.
    released_regions: list[str] = Field(default_factory=lambda: ["pk-punjab"])
    db_pool_size: int = 10  # per-process pool; multiplied by process count in the §5.8 budget
    db_max_overflow: int = 0
    db_statement_timeout_ms: int = 5000

    # Identity (P04). Production trusts exactly one managed OIDC issuer (Cognito proposed; BLOCKERS B04).
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None  # defaults to <issuer>/.well-known/jwks.json
    # Development/test-only local issuer (email + password). Refused in staging/production by the validator.
    dev_auth_enabled: bool = True
    dev_auth_issuer: str = "urn:portal:dev-local-issuer"
    dev_auth_audience: str = "portal-api"
    dev_auth_token_ttl_s: int = 900

    # Handwritten-answer evidence (W03). "local" is a private directory for development/test only (never web-served);
    # deployed roles need private object storage (S3 proposed, BLOCKERS B03), whose adapter lands with that account.
    evidence_store: Literal["local", "s3"] = "local"
    evidence_dir: str = "var/evidence"
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
    notification_email_adapter: Literal["dev_outbox", "none"] = "dev_outbox"
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
            if self.dev_auth_enabled:
                problems.append("dev_auth_enabled must be false (development identity adapter)")
            if not (self.oidc_issuer and self.oidc_audience):
                problems.append("oidc_issuer and oidc_audience are required")
            elif (
                any(m in self.oidc_issuer.lower() for m in DEV_MARKERS if m != "staging")
                or "dev-local" in self.oidc_issuer
            ):
                problems.append("oidc_issuer points at a development issuer")
            if self.evidence_store == "local":
                problems.append("evidence_store must be private object storage, not the local development directory")
            if self.trial_device_evidence is None:
                problems.append("trial_device_evidence must be set explicitly (required or fallback; roadmap §16)")
            if self.notification_email_adapter == "dev_outbox":
                problems.append("notification_email_adapter dev_outbox is development/test only")
            if self.upload_scanner == "none":
                problems.append("upload_scanner must scan uploads (clamd) in deployed roles")
            if self.written_assessor == "fixture":
                problems.append("written_assessor fixture is development/test only")
            if self.trial_ref_pepper.startswith("dev-only"):
                problems.append("trial_ref_pepper must be a deployment secret")
            if problems:
                raise ConfigurationError(f"refusing to start role={self.role.value}: " + "; ".join(problems))
        if self.db_max_overflow != 0 and self.role is Role.production:
            raise ConfigurationError("db_max_overflow must be 0 in production (connection budget, roadmap §5.8)")
        return self

    @property
    def written_pilot_only(self) -> bool:
        if self.written_release is not None:
            return self.written_release == "r0_pilot"
        return self.role in (Role.production, Role.staging)

    @property
    def jwks_url(self) -> str | None:
        if self.oidc_jwks_url:
            return self.oidc_jwks_url
        return f"{self.oidc_issuer.rstrip('/')}/.well-known/jwks.json" if self.oidc_issuer else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
