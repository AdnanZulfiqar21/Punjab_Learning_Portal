"""Operational signals and feature switches (roadmap P17.S3.T1, P17.S3.T3; OPS-01).

**Signals:** one operator view of the values the alert rules in `docs/runbooks/alerts.md` watch. Each signal has a
documented warn and alert threshold, an owner and a runbook anchor:

* queue age and dead letters for notifications, written regrades and automatic assessment;
* the teacher-marking backlog against its due dates;
* the support backlog;
* this process's connection pool.

A deployment's monitoring scrapes this endpoint (or the same queries). Real paging needs the hosting decision (B03).

**Feature switches:** optional features an operator can turn off, with a reason and an audit record, when one is
broken. Switching a feature off refuses only *new* work with 503 `FEATURE_DISABLED`. Active attempts, submissions,
marking, results and entitlements are never behind a switch, so turning a feature off never interrupts an exam or
loses work.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_engine, get_session
from portal_api.errors import AppError, NotFound
from portal_api.modules.audit.models import record

# key -> what switching it off stops (only new, optional work)
FEATURES: dict[str, str] = {
    "content_imports": "New import previews and commits (Studio → Import)",
    "content_exports": "Portable content exports",
    "prompt_packages": "Storyboard prompt-package downloads",
    "support_screenshots": "New screenshots on help requests",
    "new_practice_tests": "Building new practice tests (tests already started continue)",
    "new_written_tests": "Building new written tests (scripts already started or sealed continue)",
}


class FeatureDisabled(AppError):
    status = 503
    code = "FEATURE_DISABLED"


class FeatureSwitch(Base):
    __tablename__ = "feature_switch"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def is_enabled(db: Session, key: str) -> bool:
    row = db.get(FeatureSwitch, key)
    return row is None or row.enabled  # every feature is on unless an operator turned it off


def requires(key: str) -> Callable[[Session], None]:
    """Route dependency: refuse new work for a switched-off feature (503, retry later)."""
    assert key in FEATURES

    def check(db: Annotated[Session, Depends(get_session)]) -> None:
        if not is_enabled(db, key):
            row = db.get(FeatureSwitch, key)
            raise FeatureDisabled(
                "This feature is temporarily switched off while we fix a problem. Please try again later.",
                feature=key,
                since=row.updated_at.isoformat() if row else None,
            )

    return check


def switches(db: Session) -> list[dict[str, Any]]:
    rows = {r.key: r for r in db.scalars(select(FeatureSwitch))}
    return [
        {
            "key": k,
            "description": d,
            "enabled": rows[k].enabled if k in rows else True,
            "reason": rows[k].reason if k in rows else None,
            "updated_at": rows[k].updated_at if k in rows else None,
        }
        for k, d in FEATURES.items()
    ]


def set_switch(db: Session, actor: uuid.UUID, key: str, enabled: bool, reason: str) -> None:
    if key not in FEATURES:
        raise NotFound("Unknown feature.")
    row = db.get(FeatureSwitch, key, with_for_update=True)
    previous = row.enabled if row else True
    if row is None:
        row = FeatureSwitch(key=key, enabled=enabled, reason=reason.strip(), updated_by=actor)
        db.add(row)
    else:
        row.enabled, row.reason, row.updated_by = enabled, reason.strip(), actor
        row.updated_at = func.now()
    record(
        db,
        actor=actor,
        action="ops.feature_switched",
        target_type="feature_switch",
        target_id=key,
        details={"enabled": enabled, "previous": previous, "reason": reason.strip()},
    )
    db.commit()


# ------------------------------------------------------------------ signals
# name -> (warn, alert, owner, runbook anchor). Ages in seconds; counts as numbers.
THRESHOLDS: dict[str, tuple[float, float, str, str]] = {
    "notification_queue_age_s": (900, 3600, "platform operator", "notification-backlog"),
    "notification_dead_letters": (1, 25, "platform operator", "notification-backlog"),
    "written_regrade_queue_age_s": (1800, 7200, "platform operator", "regrade-backlog"),
    "written_regrade_failed_jobs": (1, 1, "academic operations", "regrade-backlog"),
    "auto_assessment_dead_letters": (1, 10, "platform operator", "auto-assessment"),
    "marking_overdue_cases": (1, 10, "academic operations", "marking-backlog"),
    "marking_oldest_queued_age_s": (2 * 86400, 5 * 86400, "academic operations", "marking-backlog"),
    "support_oldest_open_age_s": (86400, 3 * 86400, "support lead", "support-backlog"),
    "support_escalated_open": (1, 10, "support lead", "support-backlog"),
    "db_pool_in_use_ratio": (0.7, 0.9, "platform operator", "pool-saturation"),
    # P16.S1.T3: this process's last five minutes of requests (observability.window_summary).
    "http_server_error_ratio_5m": (0.01, 0.05, "platform operator", "error-rate"),
    "http_latency_p95_ms_5m": (800, 2000, "platform operator", "latency"),
    "submission_server_error_ratio_5m": (0.001, 0.01, "platform operator", "submission-failures"),
}
# Signals the service overview needs but nothing can measure yet: shown as unavailable with their blocker.
UNAVAILABLE: dict[str, tuple[str, str, str]] = {
    "video_playback_failure_ratio": ("B05", "platform operator", "video-failures"),
    "device_journey_budget_breaches": ("B09", "platform operator", "device-journey-budgets"),
}


def _age(db: Session, column: Any, *where: Any) -> float:
    oldest = db.scalar(select(func.min(column)).where(*where))
    if oldest is None:
        return 0.0
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return float(max(0.0, (now - oldest).total_seconds()))


def signals(db: Session) -> list[dict[str, Any]]:
    from portal_api.modules.notifications.models import NotificationDelivery
    from portal_api.modules.support.models import SupportTicket
    from portal_api.modules.written.automatic import AutoAssessment
    from portal_api.modules.written.regrade_jobs import RegradeJob
    from portal_api.modules.written.review import WrittenReviewCase

    def count(model: Any, *where: Any) -> int:
        return int(db.scalar(select(func.count()).select_from(model).where(*where)) or 0)

    pool = get_engine().pool
    size = getattr(pool, "size", lambda: 0)() + max(getattr(pool, "overflow", lambda: 0)(), 0)
    in_use = getattr(pool, "checkedout", lambda: 0)()
    values: dict[str, float] = {
        "notification_queue_age_s": _age(
            db, NotificationDelivery.next_attempt_at, NotificationDelivery.status == "queued"
        ),
        "notification_dead_letters": count(NotificationDelivery, NotificationDelivery.status == "failed"),
        "written_regrade_queue_age_s": _age(db, RegradeJob.created_at, RegradeJob.status.in_(("queued", "running"))),
        "written_regrade_failed_jobs": count(RegradeJob, RegradeJob.status == "failed"),
        "auto_assessment_dead_letters": count(AutoAssessment, AutoAssessment.status == "failed"),
        "marking_overdue_cases": count(
            WrittenReviewCase, WrittenReviewCase.status == "queued", WrittenReviewCase.due_at < func.now()
        ),
        "marking_oldest_queued_age_s": _age(db, WrittenReviewCase.opened_at, WrittenReviewCase.status == "queued"),
        "support_oldest_open_age_s": _age(db, SupportTicket.created_at, SupportTicket.status != "resolved"),
        "support_escalated_open": count(
            SupportTicket, SupportTicket.status != "resolved", SupportTicket.escalated_at.is_not(None)
        ),
        "db_pool_in_use_ratio": round(in_use / size, 3) if size else 0.0,
    }
    from portal_api import observability

    w = observability.window_summary()
    values["http_server_error_ratio_5m"] = round(w["server_error_ratio"], 4)
    values["http_latency_p95_ms_5m"] = round(w["latency_p95_ms"], 1)
    values["submission_server_error_ratio_5m"] = round(w["submission_server_error_ratio"], 4)
    out = []
    for name, value in values.items():
        warn, alert, owner, anchor = THRESHOLDS[name]
        level = "alert" if value >= alert else "warn" if value >= warn else "ok"
        out.append(
            {
                "name": name,
                "value": value,
                "level": level,
                "warn_at": warn,
                "alert_at": alert,
                "owner": owner,
                "runbook": f"docs/runbooks/alerts.md#{anchor}",
                "available": True,
                "blocker": None,
            }
        )
    for name, (blocker, owner, anchor) in UNAVAILABLE.items():
        out.append(
            {
                "name": name,
                "value": None,
                "level": "unavailable",
                "warn_at": None,
                "alert_at": None,
                "owner": owner,
                "runbook": f"docs/runbooks/alerts.md#{anchor}",
                "available": False,
                "blocker": blocker,
            }
        )
    db.rollback()
    return out
