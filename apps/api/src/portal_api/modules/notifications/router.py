"""The learner's notifications: inbox, read state, preferences and device push tokens. All private and uncached."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.modules.identity.deps import CurrentPrincipal
from portal_api.modules.notifications import service

router = APIRouter(prefix="/v1", tags=["notifications"])
DB = Annotated[Session, Depends(get_session)]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


class NotificationOut(BaseModel):
    id: uuid.UUID
    event: str
    category: Literal["service", "reminder", "promotional"]
    title: str
    body: str
    link: str | None
    created_at: datetime
    read_at: datetime | None


class InboxOut(BaseModel):
    items: list[NotificationOut]
    unread: int


class PreferencesIO(BaseModel):
    email_enabled: bool = True
    push_enabled: bool = True
    reminders_enabled: bool = Field(default=True, description="Study reminders (mock and revision)")
    promotional_opt_in: bool = Field(default=False, description="Optional news; off unless chosen")
    timezone: str = Field(default="Asia/Karachi", max_length=60, description="IANA timezone used to show times")
    quiet_start: str = Field(default="22:00", description="Local HH:MM; urgent notices still arrive")
    quiet_end: str = Field(default="07:00")


class PushTokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    platform: Literal["ios", "android"]


@router.get("/me/notifications", response_model=InboxOut)
def my_notifications(
    db: DB,
    who: CurrentPrincipal,
    response: Response,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> InboxOut:
    _private(response)
    rows, unread = service.inbox(db, who.user.id, offset, limit)
    return InboxOut(
        items=[
            NotificationOut(
                id=n.id,
                event=n.event,
                category=n.category,  # type: ignore[arg-type]
                title=n.title,
                body=n.body,
                link=n.link,
                created_at=n.created_at,
                read_at=n.read_at,
            )
            for n in rows
        ],
        unread=unread,
    )


@router.post("/me/notifications/{notification_id}/read", status_code=204)
def read_one(db: DB, who: CurrentPrincipal, notification_id: uuid.UUID) -> Response:
    service.mark_read(db, who.user.id, notification_id)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@router.post("/me/notifications/read-all", status_code=204)
def read_all(db: DB, who: CurrentPrincipal) -> Response:
    service.mark_read(db, who.user.id, None)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@router.get("/me/notification-preferences", response_model=PreferencesIO)
def get_preferences(db: DB, who: CurrentPrincipal, response: Response) -> PreferencesIO:
    _private(response)
    p = service.preferences(db, who.user.id)
    return PreferencesIO(
        email_enabled=p.email_enabled,
        push_enabled=p.push_enabled,
        reminders_enabled=p.reminders_enabled,
        promotional_opt_in=p.promotional_opt_in,
        timezone=p.timezone,
        quiet_start=p.quiet_start,
        quiet_end=p.quiet_end,
    )


@router.put("/me/notification-preferences", response_model=PreferencesIO)
def put_preferences(db: DB, who: CurrentPrincipal, body: PreferencesIO, response: Response) -> PreferencesIO:
    _private(response)
    service.save_preferences(db, who.user.id, body.model_dump())
    return get_preferences(db, who, response)


@router.post("/me/push-tokens", status_code=204, summary="Register this device for push notifications")
def add_push_token(db: DB, who: CurrentPrincipal, body: PushTokenIn) -> Response:
    service.register_push_token(db, who.user.id, body.token, body.platform)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@router.delete("/me/push-tokens", status_code=204)
def delete_push_token(db: DB, who: CurrentPrincipal, token: Annotated[str, Query(max_length=200)]) -> Response:
    service.remove_push_token(db, who.user.id, token)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
