"""Health, readiness and the runtime configuration endpoint (P03.S2.T3, roadmap §5.5).

Environment-specific public values are delivered here at runtime instead of being baked into web/native builds.
Nothing secret is ever returned.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
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
    )
