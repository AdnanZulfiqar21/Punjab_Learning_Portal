"""Analytics event dictionary and collection (roadmap P16.S2.T1; ANALYTICS-EVENTS-01).

`DICTIONARY` is the single definition of every product event: its version, meaning, where it is emitted and the exact
properties it may carry, each with a type and a meaning. `emit` refuses anything else, so an event can't quietly grow a
field that leaks private data. Never carried: private notes, passwords, tokens, emails, names, chosen options or any
answer, key or question text (`FORBIDDEN`).

* **Stable IDs:** an event's ID is derived from its name and the source object (e.g. the attempt and op), so a retried
  request or a replayed operation records it once (`ON CONFLICT DO NOTHING`).
* **Same transaction:** server events are written inside the transaction that does the work, so an event exists exactly
  when the thing happened.
* **Pseudonymous:** events carry the account ID, never contact details; they are part of the personal-data export.
* **Defined but not emitted:** `purchase.completed` waits for payments (B06). `checkpoint.answered` is defined so the
  funnel vocabulary is complete, but lesson checkpoints are private self-checks that are never stored (CHECKPOINTS-01),
  so it is not emitted.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, Index, SmallInteger, String, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_session
from portal_api.errors import NotFound
from portal_api.modules.identity.deps import CurrentPrincipal, Principal, require
from portal_api.modules.identity.permissions import Permission

NAMESPACE = uuid.UUID("6d1f3e7a-4b2c-5e8f-9a0b-1c2d3e4f5a6b")
FORBIDDEN = ("note", "password", "token", "email", "name", "phone", "option", "answer", "key", "stem", "text", "body")


@dataclass(frozen=True)
class Prop:
    type: type
    meaning: str
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventSpec:
    version: int
    meaning: str
    source: str  # server | client
    emitted: bool
    props: dict[str, Prop] = field(default_factory=dict)
    note: str = ""


DICTIONARY: dict[str, EventSpec] = {
    "lesson.started": EventSpec(
        1,
        "A signed-in learner opened a published lesson (recorded at most once per lesson per day).",
        "client",
        True,
        {
            "lesson_id": Prop(str, "The lesson item ID."),
            "language": Prop(str, "Lesson language shown.", ("en", "ur", "roman_ur")),
        },
    ),
    "lesson.completed": EventSpec(
        1,
        "A learner marked a lesson as completed (engagement, not knowledge).",
        "server",
        True,
        {"lesson_id": Prop(str, "The lesson item ID."), "version_id": Prop(str, "The lesson version read.")},
    ),
    "checkpoint.answered": EventSpec(
        1,
        "A learner answered a lesson checkpoint.",
        "client",
        False,
        {"lesson_id": Prop(str, "The lesson item ID.")},
        "Not emitted: checkpoints are private self-checks that are never stored (CHECKPOINTS-01).",
    ),
    "attempt.started": EventSpec(
        1,
        "A test attempt started.",
        "server",
        True,
        {
            "attempt_id": Prop(str, "The attempt ID."),
            "form_kind": Prop(str, "Kind of test.", ("practice", "mock", "review")),
            "question_count": Prop(int, "Questions in the test."),
            "timed": Prop(bool, "Whether the attempt has a deadline."),
        },
    ),
    "answer.saved": EventSpec(
        1,
        "An answer operation was admitted for a question (never the option chosen).",
        "server",
        True,
        {
            "attempt_id": Prop(str, "The attempt ID."),
            "position": Prop(int, "Question position in the test."),
            "state": Prop(
                str, "How the operation was admitted.", ("accepted", "stale", "locked", "late", "invalid", "finalised")
            ),
            "cleared": Prop(bool, "True when the operation cleared the answer."),
            "via": Prop(str, "How the operation arrived (save, submit)."),
        },
    ),
    "attempt.submitted": EventSpec(
        1,
        "A test attempt was finalised.",
        "server",
        True,
        {
            "attempt_id": Prop(str, "The attempt ID."),
            "reason": Prop(str, "How it ended (e.g. manual, deadline)."),
            "answered": Prop(int, "Questions answered."),
            "question_count": Prop(int, "Questions in the test."),
        },
    ),
    "score.version_created": EventSpec(
        1,
        "A score version was recorded for an attempt (first scoring or a reviewed correction).",
        "server",
        True,
        {
            "attempt_id": Prop(str, "The attempt ID."),
            "version": Prop(int, "Score version number (1 = first scoring)."),
            "status": Prop(str, "Scoring status (e.g. scored, not_scorable)."),
            "correction": Prop(bool, "True when created by a reviewed correction."),
        },
    ),
    "trial.decided": EventSpec(
        1,
        "A free-trial request was decided.",
        "server",
        True,
        {
            "state": Prop(str, "The decision (e.g. granted, active, device_used, review_required)."),
            "surface": Prop(str, "web, android or ios."),
        },
    ),
    "purchase.completed": EventSpec(
        1,
        "A provider-confirmed purchase completed.",
        "server",
        False,
        {"product_code": Prop(str, "The product bought.")},
        "Not emitted until a payment provider exists (B06).",
    ),
}


class AnalyticsEvent(Base):
    __tablename__ = "analytics_event"
    __table_args__ = (Index("ix_analytics_event_name_time", "name", "occurred_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    version: Mapped[int] = mapped_column(SmallInteger)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventRejected(ValueError):
    pass


def validate(name: str, props: dict[str, Any]) -> EventSpec:
    spec = DICTIONARY.get(name)
    if spec is None:
        raise EventRejected(f"unknown event {name!r}")
    if not spec.emitted:
        raise EventRejected(f"{name} is defined but not emitted: {spec.note}")
    unknown = set(props) - set(spec.props)
    missing = set(spec.props) - set(props)
    if unknown or missing:
        raise EventRejected(f"{name}: unknown {sorted(unknown)}, missing {sorted(missing)}")
    for k, v in props.items():
        p = spec.props[k]
        if not isinstance(v, p.type) or (p.type is int and isinstance(v, bool)):
            raise EventRejected(f"{name}.{k} must be {p.type.__name__}")
        if p.choices and v not in p.choices:
            raise EventRejected(f"{name}.{k} must be one of {p.choices}")
    return spec


def emit(
    db: Session, name: str, *, key: str, user_id: uuid.UUID | None, at: datetime | None = None, **props: Any
) -> None:
    """Record one event inside the caller's transaction; the same (name, key) is recorded once."""
    spec = validate(name, props)
    db.execute(
        insert(AnalyticsEvent)
        .values(
            id=uuid.uuid5(NAMESPACE, f"{name}:{key}"),
            name=name,
            version=spec.version,
            user_id=user_id,
            occurred_at=at if at is not None else func.now(),
            properties=props,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )


def dictionary_document() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "version": s.version,
            "meaning": s.meaning,
            "source": s.source,
            "emitted": s.emitted,
            "note": s.note or None,
            "properties": [
                {"name": k, "type": p.type.__name__, "meaning": p.meaning, "choices": list(p.choices) or None}
                for k, p in s.props.items()
            ],
        }
        for name, s in DICTIONARY.items()
    ]


# ------------------------------------------------------------------ routes
router = APIRouter(prefix="/v1", tags=["analytics"])
DB = Annotated[Session, Depends(get_session)]
Viewer = Annotated[Principal, Depends(require(Permission.view_business_overview))]


class LessonStartedIn(BaseModel):
    lesson_id: uuid.UUID
    language: Literal["en", "ur", "roman_ur"] = "en"


@router.post("/me/events/lesson-started", status_code=204, summary="Record that you opened a lesson (once a day)")
def lesson_started(db: DB, who: CurrentPrincipal, body: LessonStartedIn) -> Response:
    from portal_api.modules.content.models import Availability, ContentItem

    item = db.get(ContentItem, body.lesson_id)
    if item is None or item.kind != "lesson" or item.availability != Availability.live.value:
        raise NotFound("Lesson not found.")
    day = db.execute(select(func.current_date())).scalar_one()
    emit(
        db,
        "lesson.started",
        key=f"{who.user.id}:{item.id}:{day}",
        user_id=who.user.id,
        lesson_id=str(item.id),
        language=body.language,
    )
    db.commit()
    return Response(status_code=204)


@router.get("/admin/analytics/dictionary", summary="The analytics event dictionary (owner/admin, finance; MFA)")
def analytics_dictionary(who: Viewer, response: Response) -> list[dict[str, Any]]:
    response.headers["Cache-Control"] = "private, no-store"
    return dictionary_document()
