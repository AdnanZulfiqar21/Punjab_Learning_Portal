from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.modules.curriculum import service
from portal_api.modules.curriculum.schemas import BookOut, CatalogueOut, ChapterOut, SearchOut

router = APIRouter(prefix="/v1", tags=["curriculum"])
DB = Annotated[Session, Depends(get_session)]
# Public published structure: cacheable by shared caches for a short time (roadmap §5.3).
PUBLIC_CACHE = "public, max-age=60, stale-while-revalidate=300"


@router.get("/catalogue", response_model=CatalogueOut, summary="Grades → subjects → books (Class XI and XII separate)")
def catalogue(db: DB, response: Response) -> CatalogueOut:
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return service.get_catalogue(db)


@router.get("/grades/{grade}/subjects/{subject}/book", response_model=BookOut, summary="The book for one grade+subject")
def book_for(
    db: DB,
    response: Response,
    grade: Annotated[int, Path(ge=11, le=12)],
    subject: Annotated[str, Path(min_length=2, max_length=40)],
) -> BookOut:
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return service.get_book_for(db, grade, subject)


@router.get("/books/{book_id}", response_model=BookOut)
def book(db: DB, response: Response, book_id: uuid.UUID) -> BookOut:
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return service.get_book(db, book_id)


@router.get("/chapters/{chapter_id}", response_model=ChapterOut)
def chapter(db: DB, response: Response, chapter_id: uuid.UUID) -> ChapterOut:
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return service.get_chapter(db, chapter_id)


@router.get(
    "/search", response_model=SearchOut, summary="Search chapters and topics; every hit is labelled with its grade"
)
def search(
    db: DB,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    grade: Annotated[int | None, Query(ge=11, le=12)] = None,
    subject: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchOut:
    return service.search(db, q, grade, subject, limit)
