"""Read-side curriculum queries. Grade is always part of the identity of a book; nothing merges XI and XII."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from portal_api.errors import NotFound
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Subject, Topic
from portal_api.modules.curriculum.schemas import (
    BookOut,
    BookSummary,
    Breadcrumb,
    CatalogueOut,
    ChapterOut,
    ChapterSummary,
    GradeCatalogue,
    GradeOut,
    SearchHit,
    SearchOut,
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


def get_catalogue(session: Session) -> CatalogueOut:
    grades = session.scalars(select(Grade).order_by(Grade.number)).all()
    subjects = session.scalars(select(Subject).where(Subject.active).order_by(Subject.display_order)).all()
    counts: dict[uuid.UUID, int] = {
        bid: n for bid, n in session.execute(select(Chapter.book_id, func.count()).group_by(Chapter.book_id))
    }
    by_key: dict[tuple[uuid.UUID, uuid.UUID], list[BookEdition]] = defaultdict(list)
    for b in session.scalars(select(BookEdition)).unique().all():
        by_key[(b.grade_id, b.subject_id)].append(b)
    out = []
    for g in grades:
        items = []
        for s in subjects:
            books = [
                BookSummary(
                    id=b.id,
                    title=b.title,
                    source_id=b.source.source_id,
                    chapter_label=b.chapter_label,
                    chapter_count=counts.get(b.id, 0),
                    completeness=b.source.completeness,
                )
                for b in by_key.get((g.id, s.id), [])
            ]
            items.append(SubjectInGrade(subject=SubjectOut.model_validate(s), books=books))
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
    ]


def get_book_for(session: Session, grade: int, subject: str) -> BookOut:
    code = normalise_subject(subject)
    book = (
        session.scalars(
            select(BookEdition)
            .join(Grade, BookEdition.grade_id == Grade.id)
            .join(Subject, BookEdition.subject_id == Subject.id)
            .where(Grade.number == grade, Subject.code == code, Subject.active)
        )
        .unique()
        .first()
    )
    if book is None:
        raise NotFound(f"No Class {grade} book is available for subject '{subject}'.")
    return _book_out(session, book)


def get_book(session: Session, book_id: uuid.UUID) -> BookOut:
    book = session.get(BookEdition, book_id)
    if book is None:
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
    if ch is None:
        raise NotFound("Chapter not found.")
    book = ch.book
    siblings = [c.id for c in book.chapters]
    i = siblings.index(ch.id)
    nodes: dict[uuid.UUID, TopicNode] = {}
    roots: list[TopicNode] = []
    for t in ch.topics:  # ordered by display_order; parents precede children
        node = TopicNode(
            id=t.id, number=t.number, title=t.title, depth=t.depth, pdf_page=t.pdf_page, points=t.points, children=[]
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


# Typo tolerance without unrelated suffix matches (measured on real titles, e.g. "photosyntesis"→0.71,
# "Synthesis of …"→0.47 for "photosynthesis"). The full relevance benchmark is P11 search work.
FUZZY_THRESHOLD = 0.65

SEARCH_SQL = text("""
WITH q AS (SELECT CAST(:q AS text) AS q)
SELECT kind, id, chapter_id, title, number, chapter_title, grade, subject_code, subject_name, pdf_page, score FROM (
  SELECT 'topic' AS kind, t.id, c.id AS chapter_id, t.title, t.number, c.title AS chapter_title, g.number AS grade,
         s.code AS subject_code, s.name AS subject_name, t.pdf_page,
         CASE WHEN t.title ILIKE '%' || q.q || '%' THEN 1.0 ELSE strict_word_similarity(q.q, t.title) END AS score
    FROM topic t JOIN chapter c ON c.id = t.chapter_id JOIN book_edition b ON b.id = c.book_id
    JOIN grade g ON g.id = b.grade_id JOIN subject s ON s.id = b.subject_id, q
   WHERE s.active AND (t.title ILIKE '%' || q.q || '%' OR strict_word_similarity(q.q, t.title) >= :fuzzy)
         AND (CAST(:grade AS int) IS NULL OR g.number = CAST(:grade AS int))
         AND (CAST(:subject AS text) IS NULL OR s.code = CAST(:subject AS text))
  UNION ALL
  SELECT 'chapter', c.id, c.id, c.title, CAST(c.number AS text), c.title, g.number, s.code, s.name, c.pdf_start,
         CASE WHEN c.title ILIKE '%' || q.q || '%' THEN 1.05 ELSE strict_word_similarity(q.q, c.title) + 0.05 END
    FROM chapter c JOIN book_edition b ON b.id = c.book_id JOIN grade g ON g.id = b.grade_id
    JOIN subject s ON s.id = b.subject_id, q
   WHERE s.active AND (c.title ILIKE '%' || q.q || '%' OR strict_word_similarity(q.q, c.title) >= :fuzzy)
         AND (CAST(:grade AS int) IS NULL OR g.number = CAST(:grade AS int))
         AND (CAST(:subject AS text) IS NULL OR s.code = CAST(:subject AS text))
) hits ORDER BY score DESC, grade, title LIMIT :limit
""")


def search(session: Session, q: str, grade: int | None, subject: str | None, limit: int = 20) -> SearchOut:
    subj = normalise_subject(subject) if subject else None
    rows = session.execute(
        SEARCH_SQL, {"q": q.strip(), "grade": grade, "subject": subj, "limit": limit, "fuzzy": FUZZY_THRESHOLD}
    ).mappings()
    return SearchOut(
        query=q, grade=grade, subject=subj, hits=[SearchHit(**{**r, "score": float(r["score"])}) for r in rows]
    )
