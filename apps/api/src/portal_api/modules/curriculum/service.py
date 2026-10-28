"""Read-side curriculum queries. Grade is always part of the identity of a book; nothing merges XI and XII."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.days import local_date
from portal_api.errors import Conflict, Gone, NotFound
from portal_api.modules.curriculum.editions import covers
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Subject, Topic
from portal_api.modules.curriculum.regions import book_is_released, released_grade
from portal_api.modules.curriculum.schemas import (
    BookOut,
    BookSummary,
    Breadcrumb,
    CatalogueOut,
    ChapterOut,
    ChapterSummary,
    GradeCatalogue,
    GradeOut,
    SourceRef,
    SubjectInGrade,
    SubjectOut,
    TopicNode,
)

SUBJECT_ALIASES = {
    "maths": "mathematics",
    "math": "mathematics",
    "cs": "computer_science",
    "computer": "computer_science",
    "bio": "biology",
    "chem": "chemistry",
    "phy": "physics",
}


def normalise_subject(code: str) -> str:
    c = code.strip().lower().replace("-", "_").replace(" ", "_")
    return SUBJECT_ALIASES.get(c, c)


def _breadcrumb(book: BookEdition) -> Breadcrumb:
    return Breadcrumb(
        grade=GradeOut.model_validate(book.grade),
        subject=SubjectOut.model_validate(book.subject),
        book_id=book.id,
        book_title=book.title,
        source_id=book.source.source_id,
        chapter_label=book.chapter_label,
    )


def _today(session: Session) -> date:
    now: datetime = session.execute(select(func.now())).scalar_one()
    return local_date(now)


def _current(books: list[BookEdition], day: date) -> list[BookEdition]:
    return [book for book in books if covers(book.effective_from, book.effective_until, day)]


def get_catalogue(session: Session) -> CatalogueOut:
    grades = session.scalars(select(Grade).where(released_grade()).order_by(Grade.number)).all()
    subjects = session.scalars(select(Subject).where(Subject.active).order_by(Subject.display_order)).all()
    counts: dict[uuid.UUID, int] = {
        bid: n
        for bid, n in session.execute(
            select(Chapter.book_id, func.count()).where(Chapter.retired_at.is_(None)).group_by(Chapter.book_id)
        )
    }
    by_key: dict[tuple[uuid.UUID, uuid.UUID], list[BookEdition]] = defaultdict(list)
    today = _today(session)
    for b in session.scalars(select(BookEdition)).unique().all():
        if covers(b.effective_from, b.effective_until, today):
            by_key[(b.grade_id, b.subject_id)].append(b)
    out = []
    for g in grades:
        items = []
        for s in subjects:
            matching = by_key.get((g.id, s.id), [])
            conflict = len(matching) > 1
            books = (
                []
                if conflict
                else [
                    BookSummary(
                        id=b.id,
                        title=b.title,
                        source_id=b.source.source_id,
                        chapter_label=b.chapter_label,
                        chapter_count=counts.get(b.id, 0),
                        completeness=b.source.completeness,
                    )
                    for b in matching
                ]
            )
            items.append(SubjectInGrade(subject=SubjectOut.model_validate(s), books=books, edition_conflict=conflict))
        out.append(GradeCatalogue(grade=GradeOut.model_validate(g), subjects=items))
    return CatalogueOut(region="pk-punjab", scope_decision="SCOPE-01", grades=out)


def _chapter_summaries(session: Session, book: BookEdition) -> list[ChapterSummary]:
    topic_counts: dict[uuid.UUID, int] = {
        cid: n
        for cid, n in session.execute(
            select(Topic.chapter_id, func.count())
            .join(Chapter)
            .where(Chapter.book_id == book.id)
            .group_by(Topic.chapter_id)
        )
    }
    return [
        ChapterSummary(
            id=c.id,
            display_order=c.display_order,
            number=c.number,
            contents_number=c.contents_number,
            title=c.title,
            status=c.status,
            pdf_start=c.pdf_start,
            pdf_end=c.pdf_end,
            printed_start=c.printed_start,
            printed_end=c.printed_end,
            topic_count=topic_counts.get(c.id, 0),
            visual_count=c.visual_count,
            assessment_counts=c.assessment_counts,
            content_state=c.content_state,
        )
        for c in book.chapters
        if c.retired_at is None
    ]


def get_book_for(session: Session, grade: int, subject: str) -> BookOut:
    return _book_out(session, book_for(session, grade, subject))


def book_for(session: Session, grade: int, subject: str) -> BookEdition:
    """The one edition of this class's book in this subject that is effective today."""
    code = normalise_subject(subject)
    books = (
        session.scalars(
            select(BookEdition)
            .join(Grade, BookEdition.grade_id == Grade.id)
            .join(Subject, BookEdition.subject_id == Subject.id)
            .where(Grade.number == grade, Subject.code == code, Subject.active, released_grade())
        )
        .unique()
        .all()
    )
    current = _current(list(books), _today(session))
    if len(current) > 1:
        raise Conflict("More than one edition of this book is effective today, so none is chosen.")
    if not current:
        raise NotFound(f"No Class {grade} book is available for subject '{subject}'.")
    return current[0]


def get_book(session: Session, book_id: uuid.UUID) -> BookOut:
    book = session.get(BookEdition, book_id)
    if book is None or not book_is_released(session, book):  # REGION-01: unreleased regions aren't discoverable
        raise NotFound("Book not found.")
    return _book_out(session, book)


def _book_out(session: Session, book: BookEdition) -> BookOut:
    return BookOut(
        breadcrumb=_breadcrumb(book),
        completeness=book.source.completeness,
        missing_pages=[str(p) for p in book.source.missing_pages],
        edition=book.source.edition,
        authority=book.source.authority,
        chapters=_chapter_summaries(session, book),
    )


def get_chapter(session: Session, chapter_id: uuid.UUID) -> ChapterOut:
    ch = session.get(Chapter, chapter_id)
    if ch is None or not book_is_released(session, ch.book):  # REGION-01
        raise NotFound("Chapter not found.")
    if ch.retired_at is not None:
        raise Gone("This chapter is no longer part of the current textbook catalogue.")
    book = ch.book
    siblings = [c.id for c in book.chapters if c.retired_at is None]
    i = siblings.index(ch.id)
    nodes: dict[uuid.UUID, TopicNode] = {}
    roots: list[TopicNode] = []
    for t in ch.topics:  # ordered by display_order; parents precede children
        if t.retired_at is not None:
            continue
        node = TopicNode(
            id=t.id,
            number=t.number,
            title=t.title,
            kind=t.kind,
            depth=t.depth,
            pdf_page=t.pdf_page,
            points=t.points,
            children=[],
        )
        nodes[t.id] = node
        if t.parent_id and t.parent_id in nodes:
            nodes[t.parent_id].children.append(node)
        else:
            roots.append(node)
    return ChapterOut(
        id=ch.id,
        breadcrumb=_breadcrumb(book),
        number=ch.number,
        contents_number=ch.contents_number,
        title=ch.title,
        status=ch.status,
        main_concept=ch.main_concept,
        slo_codes=ch.slo_codes,
        key_terms=ch.key_terms,
        visual_count=ch.visual_count,
        assessment_counts=ch.assessment_counts,
        content_state=ch.content_state,
        source=SourceRef(
            source_id=book.source.source_id,
            file=book.source.file_path,
            sha256=book.source.sha256,
            pdf_start=ch.pdf_start,
            pdf_end=ch.pdf_end,
            printed_start=ch.printed_start,
            printed_end=ch.printed_end,
            page_rule=book.source.page_rule,
        ),
        topics=roots,
        previous_chapter_id=siblings[i - 1] if i > 0 else None,
        next_chapter_id=siblings[i + 1] if i + 1 < len(siblings) else None,
    )
