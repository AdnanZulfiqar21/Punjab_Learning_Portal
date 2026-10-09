"""Health, readiness and the runtime configuration endpoint (P03.S2.T3, roadmap §5.5).

Environment-specific public values are delivered here at runtime instead of being baked into web/native builds.
Nothing secret is ever returned.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.config import Settings, get_settings
from portal_api.db import get_session

router = APIRouter(tags=["system"])


class RuntimeConfig(BaseModel):
    role: str
    build_id: str
    api_origin: str
    media_origin: str
    region: str
    active_grades: list[int]
    active_subjects: list[str]
    scope_decision: str
    # Only methods this deployment can actually perform. dev_password exists only in development/test (IMPL-09).
    sign_in_methods: list[str]


@router.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
def readyz(db: Annotated[Session, Depends(get_session)], response: Response) -> dict[str, str]:
    try:
        db.execute(text("select 1"))
        migrated = db.execute(text("select version_num from alembic_version")).scalar_one_or_none()
    except Exception:
        response.status_code = 503
        return {"status": "unavailable", "database": "unreachable"}
    if not migrated:
        response.status_code = 503
        return {"status": "unavailable", "database": "not migrated"}
    return {"status": "ready", "migration": str(migrated)}


@router.get("/v1/runtime-config", response_model=RuntimeConfig)
def runtime_config(settings: Annotated[Settings, Depends(get_settings)]) -> RuntimeConfig:
    return RuntimeConfig(
        role=settings.role.value,
        build_id=settings.build_id,
        api_origin=settings.public_api_origin,
        media_origin=settings.public_media_origin,
        region="pk-punjab",
        active_grades=[11, 12],
        active_subjects=["biology", "chemistry", "physics", "computer_science", "mathematics"],
        scope_decision="SCOPE-01",
        sign_in_methods=(["oidc"] if settings.oidc_issuer else [])
        + (["dev_password"] if settings.dev_auth_enabled else []),
    )


# ------------------------------------------------------------------ operations (P17.S3.T1/T3, OPS-01)
def _operator() -> object:
    from portal_api.modules.identity.deps import require
    from portal_api.modules.identity.permissions import Permission

    return require(Permission.operate_platform)


class SignalOut(BaseModel):
    name: str
    value: float
    level: str
    warn_at: float
    alert_at: float
    owner: str
    runbook: str


class FeatureOut(BaseModel):
    key: str
    description: str
    enabled: bool
    reason: str | None
    updated_at: datetime | None


class FeatureIn(BaseModel):
    enabled: bool
    reason: str = Field(min_length=10, max_length=1000)


@router.get("/v1/ops/signals", response_model=list[SignalOut], summary="Alert signals with thresholds (operators, MFA)")
def ops_signals(
    db: Annotated[Session, Depends(get_session)], who: Annotated[Any, Depends(_operator())]
) -> list[SignalOut]:
    from portal_api.modules.system import operations

    return [SignalOut(**s) for s in operations.signals(db)]


@router.get("/v1/ops/features", response_model=list[FeatureOut], summary="Optional feature switches (operators)")
def ops_features(
    db: Annotated[Session, Depends(get_session)], who: Annotated[Any, Depends(_operator())]
) -> list[FeatureOut]:
    from portal_api.modules.system import operations

    return [FeatureOut(**f) for f in operations.switches(db)]


@router.put(
    "/v1/ops/features/{key}",
    response_model=list[FeatureOut],
    summary="Turn an optional feature off or on (operators, MFA, reason; audited). Active work is never interrupted",
)
def ops_set_feature(
    key: str, body: FeatureIn, db: Annotated[Session, Depends(get_session)], who: Annotated[Any, Depends(_operator())]
) -> list[FeatureOut]:
    from portal_api.modules.system import operations

    operations.set_switch(db, who.user.id, key, body.enabled, body.reason)
    return [FeatureOut(**f) for f in operations.switches(db)]
