"""Integrations and quotas (roadmap P16.S3.T2; INTEGRATIONS-01).

One operator view of every external provider the portal uses or will use: which adapter is configured, whether that is
a development stand-in, a live connection or not available yet (with the blocker), a safe health check where one is
possible without side effects, 24-hour usage from the portal's own records, and a daily budget with warn/alert levels.

Never shown: secrets, keys, URLs with credentials or learner data. Development adapters are refused in deployed roles
by the configuration validator, so `development` here can only appear in development and test.
"""

from __future__ import annotations

import os
import socket
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.config import get_settings
from portal_api.db import get_session
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission

WARN_AT, ALERT_AT = 0.8, 1.0


def _clamd_ping(host: str, port: int) -> str:
    try:
        with socket.create_connection((host, port), timeout=2) as conn:
            conn.sendall(b"zPING\x00")
            return "ok" if conn.recv(16).startswith(b"PONG") else "failing"
    except OSError:
        return "failing"


def _writable(path: Path) -> str:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return "ok" if os.access(path, os.W_OK) else "failing"
    except OSError:
        return "failing"


def _level(used: int, budget: int | None) -> tuple[float | None, str]:
    if not budget:
        return None, "ok"
    ratio = used / budget
    return round(ratio, 3), "alert" if ratio >= ALERT_AT else "warn" if ratio >= WARN_AT else "ok"


def overview(db: Session) -> list[dict[str, Any]]:
    from portal_api.modules.notifications.models import NotificationDelivery
    from portal_api.modules.written.automatic import AutoAssessment

    s = get_settings()
    since = db.execute(select(func.now())).scalar_one() - timedelta(hours=24)

    def deliveries(channel: str) -> dict[str, int]:
        return {
            status: int(n)
            for status, n in db.execute(
                select(NotificationDelivery.status, func.count())
                .where(NotificationDelivery.channel == channel, NotificationDelivery.created_at >= since)
                .group_by(NotificationDelivery.status)
            ).all()
        }

    email = deliveries("email")
    push = deliveries("push")
    assessed = int(
        db.scalar(select(func.count()).select_from(AutoAssessment).where(AutoAssessment.created_at >= since)) or 0
    )
    evidence_root = Path(s.evidence_dir)
    if not evidence_root.is_absolute():
        evidence_root = Path(__file__).resolve().parents[4] / evidence_root
    rows: list[dict[str, Any]] = [
        {
            "key": "identity",
            "name": "Sign-in (identity provider)",
            "adapter": "development issuer" if s.dev_auth_enabled else "OIDC",
            "mode": "development" if s.dev_auth_enabled else "live",
            "blocker": None,
            "health": "not_checked",
            "usage_24h": {},
            "budget_daily": None,
        },
        {
            "key": "email",
            "name": "Email delivery",
            "adapter": s.notification_email_adapter,
            "mode": {"dev_outbox": "development", "none": "unavailable"}.get(s.notification_email_adapter, "live"),
            "blocker": "B04" if s.notification_email_adapter == "none" else None,
            "health": "not_checked",
            "usage_24h": email,
            "budget_daily": s.email_daily_budget,
        },
        {
            "key": "push",
            "name": "Push notifications",
            "adapter": "none",
            "mode": "unavailable",
            "blocker": "B07",
            "health": "not_checked",
            "usage_24h": push,
            "budget_daily": None,
        },
        {
            "key": "object_storage",
            "name": "Private file storage",
            "adapter": s.evidence_store,
            "mode": "development" if s.evidence_store == "local" else "unavailable",  # the S3 adapter lands with B03
            "blocker": None if s.evidence_store == "local" else "B03",
            "health": _writable(evidence_root) if s.evidence_store == "local" else "not_checked",
            "usage_24h": {},
            "budget_daily": None,
        },
        {
            "key": "upload_scanner",
            "name": "Upload scanning (ClamAV)",
            "adapter": s.upload_scanner,
            "mode": "live" if s.upload_scanner == "clamd" else "development",
            "blocker": None,
            "health": _clamd_ping(s.clamd_host, s.clamd_port) if s.upload_scanner == "clamd" else "not_checked",
            "usage_24h": {},
            "budget_daily": None,
        },
        {
            "key": "written_assessor",
            "name": "Automatic written assessment",
            "adapter": s.written_assessor,
            "mode": "development" if s.written_assessor == "fixture" else "unavailable",
            "blocker": "B10" if s.written_assessor == "none" else None,
            "health": "not_checked",
            "usage_24h": {"assessments": assessed} if assessed else {},
            "budget_daily": s.assessor_daily_budget,
        },
        {
            "key": "device_attestation",
            "name": "Trial device evidence",
            "adapter": s.trial_device_evidence or "unset",
            "mode": "unavailable",
            "blocker": "B07/B08",
            "health": "not_checked",
            "usage_24h": {},
            "budget_daily": None,
        },
        {
            "key": "payments",
            "name": "Payments",
            "adapter": "none",
            "mode": "unavailable",
            "blocker": "B06",
            "health": "not_checked",
            "usage_24h": {},
            "budget_daily": None,
        },
        {
            "key": "media",
            "name": "Video delivery",
            "adapter": "none",
            "mode": "unavailable",
            "blocker": "B05",
            "health": "not_checked",
            "usage_24h": {},
            "budget_daily": None,
        },
    ]
    for r in rows:
        used = sum(r["usage_24h"].values())
        r["budget_used_ratio"], r["level"] = _level(used, r["budget_daily"])
        if r["health"] == "failing":
            r["level"] = "alert"
    db.rollback()
    return rows


# ------------------------------------------------------------------ route
router = APIRouter(prefix="/v1/ops", tags=["operations"])
Operator = Annotated[Principal, Depends(require(Permission.operate_platform))]


class IntegrationOut(BaseModel):
    key: str
    name: str
    adapter: str
    mode: str
    blocker: str | None
    health: str
    usage_24h: dict[str, int]
    budget_daily: int | None
    budget_used_ratio: float | None
    level: str


@router.get(
    "/integrations", response_model=list[IntegrationOut], summary="External providers: mode, health, usage, budget"
)
def integrations(
    db: Annotated[Session, Depends(get_session)], who: Operator, response: Response
) -> list[IntegrationOut]:
    response.headers["Cache-Control"] = "private, no-store"
    return [IntegrationOut(**r) for r in overview(db)]
