"""Runtime configuration and the startup validator (P03.S2.T3, roadmap §5.5).

Every environment-specific value comes from the environment at runtime. The validator refuses to start a
production role with development/staging adapters, URLs or credentials, so a promoted image can never
silently carry them.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

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
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3100", "http://127.0.0.1:3100"])
    db_pool_size: int = 10  # per-process pool; multiplied by process count in the §5.8 budget
    db_max_overflow: int = 0
    db_statement_timeout_ms: int = 5000

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
            if problems:
                raise ConfigurationError(f"refusing to start role={self.role.value}: " + "; ".join(problems))
        if self.db_max_overflow != 0 and self.role is Role.production:
            raise ConfigurationError("db_max_overflow must be 0 in production (connection budget, roadmap §5.8)")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
