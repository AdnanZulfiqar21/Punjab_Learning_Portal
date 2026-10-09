"""Help articles (public read; staff authoring) and service status (public read; operator updates)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.modules.help import service
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission

router = APIRouter(prefix="/v1", tags=["help"])
DB = Annotated[Session, Depends(get_session)]
Operator = Annotated[Principal, Depends(require(Permission.operate_platform))]
# OCT9-06: help authoring is authorised before the body is read (the service re-checks, including MFA to publish).
HelpStaff = Annotated[Principal, Depends(require(Permission.manage_help))]


class ArticleSummary(BaseModel):
    slug: str
    locale: Literal["en", "ur"]
    title: str
    summary: str
    tags: list[str]
    version: int


class ArticleOut(ArticleSummary):
    body: dict[str, Any] = Field(description="Content blocks (heading, paragraph, list, callout)")
    published_at: datetime | None
    fallback_locale: bool = Field(description="True when the requested language had no version, so English is shown")


class DraftIn(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    locale: Literal["en", "ur"] = "en"
    title: str
    summary: str
    markdown: str = Field(min_length=10, max_length=50_000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class StaffArticle(BaseModel):
    id: uuid.UUID
    slug: str
    locale: str
    status: Literal["draft", "published", "retired"]
    title: str | None
    working_version: int | None
    published: bool
    unpublished_changes: bool


class IncidentIn(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    message: str = Field(min_length=10, max_length=2000)
    components: list[str] = Field(default_factory=list, max_length=10)


class IncidentUpdateIn(BaseModel):
    status: Literal["investigating", "identified", "monitoring", "resolved"]
    message: str = Field(min_length=5, max_length=2000)


class IncidentUpdateOut(BaseModel):
    status: str
    message: str
    at: datetime


class IncidentOut(BaseModel):
    id: uuid.UUID
    title: str
    status: Literal["investigating", "identified", "monitoring", "resolved"]
    components: list[str]
    started_at: datetime
    resolved_at: datetime | None
    updates: list[IncidentUpdateOut]


class StatusOut(BaseModel):
    operational: bool = Field(description="False while any incident is unresolved")
    incidents: list[IncidentOut]


def _summary(a: Any, v: Any) -> dict[str, Any]:
    return {
        "slug": a.slug,
        "locale": a.locale,
        "title": v.title,
        "summary": v.summary,
        "tags": v.tags,
        "version": v.number,
    }


@router.get("/help/articles", response_model=list[ArticleSummary], summary="Search published help articles")
def list_articles(
    db: DB,
    response: Response,
    q: Annotated[str, Query(max_length=200)] = "",
    locale: Literal["en", "ur"] = "en",
    limit: Annotated[int, Query(ge=1, le=50)] = 30,
) -> list[ArticleSummary]:
    response.headers["Cache-Control"] = "public, max-age=60"
    return [ArticleSummary(**_summary(a, v)) for a, v in service.search(db, q, locale, limit)]


@router.get("/help/articles/{slug}", response_model=ArticleOut)
def get_article(db: DB, slug: str, response: Response, locale: Literal["en", "ur"] = "en") -> ArticleOut:
    response.headers["Cache-Control"] = "public, max-age=60"
    a, v, fallback = service.read(db, slug, locale)
    return ArticleOut(**_summary(a, v), body=v.body, published_at=v.published_at, fallback_locale=fallback)


@router.get("/studio/help/articles", response_model=list[StaffArticle])
def staff_articles(db: DB, who: HelpStaff, response: Response) -> list[StaffArticle]:
    response.headers["Cache-Control"] = "private, no-store"
    return [
        StaffArticle(
            id=a.id,
            slug=a.slug,
            locale=a.locale,
            status=a.status,  # type: ignore[arg-type]
            title=v.title if v else None,
            working_version=v.number if v else None,
            published=a.published_version_id is not None,
            unpublished_changes=a.working_version_id != a.published_version_id,
        )
        for a, v in service.staff_list(db, who)
    ]


@router.put("/studio/help/articles", response_model=StaffArticle, summary="Save a draft (a new version)")
def save_article(db: DB, who: HelpStaff, body: DraftIn, response: Response) -> StaffArticle:
    response.headers["Cache-Control"] = "private, no-store"
    a = service.save_draft(
        db,
        who,
        slug=body.slug,
        locale=body.locale,
        title=body.title,
        summary=body.summary,
        markdown=body.markdown,
        tags=body.tags,
    )
    return next(x for x in staff_articles(db, who, response) if x.id == a.id)


@router.post("/studio/help/articles/{article_id}/publish", response_model=StaffArticle, summary="Publish (MFA)")
def publish_article(db: DB, who: HelpStaff, article_id: uuid.UUID, response: Response) -> StaffArticle:
    service.publish(db, who, article_id)
    return next(x for x in staff_articles(db, who, response) if x.id == article_id)


@router.post("/studio/help/articles/{article_id}/retire", response_model=StaffArticle, summary="Retire (MFA)")
def retire_article(db: DB, who: HelpStaff, article_id: uuid.UUID, response: Response) -> StaffArticle:
    service.retire(db, who, article_id)
    return next(x for x in staff_articles(db, who, response) if x.id == article_id)


def _incident(i: Any, updates: list[Any]) -> IncidentOut:
    return IncidentOut(
        id=i.id,
        title=i.title,
        status=i.status,
        components=i.components,
        started_at=i.started_at,
        resolved_at=i.resolved_at,
        updates=[IncidentUpdateOut(status=u.status, message=u.message, at=u.at) for u in updates],
    )


@router.get("/status", response_model=StatusOut, summary="Known incidents (public; no sign-in needed)")
def status(db: DB, response: Response) -> StatusOut:
    response.headers["Cache-Control"] = "public, max-age=30"
    rows = service.current_incidents(db)
    return StatusOut(
        operational=all(i.status == "resolved" for i, _ in rows), incidents=[_incident(i, u) for i, u in rows]
    )


@router.post("/ops/incidents", response_model=IncidentOut, status_code=201)
def open_incident(db: DB, who: Operator, body: IncidentIn, response: Response) -> IncidentOut:
    response.headers["Cache-Control"] = "private, no-store"
    i = service.open_incident(db, who, body.title, body.message, body.components)
    return next(_incident(x, u) for x, u in service.current_incidents(db) if x.id == i.id)


@router.post("/ops/incidents/{incident_id}/updates", response_model=IncidentOut)
def update_incident(
    db: DB, who: Operator, incident_id: uuid.UUID, body: IncidentUpdateIn, response: Response
) -> IncidentOut:
    response.headers["Cache-Control"] = "private, no-store"
    service.update_incident(db, who, incident_id, body.status, body.message)
    return next(_incident(x, u) for x, u in service.current_incidents(db) if x.id == incident_id)
