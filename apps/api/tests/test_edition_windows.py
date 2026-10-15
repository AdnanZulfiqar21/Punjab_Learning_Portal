"""Edition windows (P05.S1.T3).

A second textbook edition is a technical fixture in the test database. It is not a real Punjab edition, and the test
removes it. Real edition years are not chosen here.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from portal_api.days import local_date
from portal_api.db import get_sessionmaker
from portal_api.modules.curriculum.editions import covers
from portal_api.modules.curriculum.models import BookEdition, Grade, SourceDocument, Subject


def test_a_window_includes_its_start_and_excludes_its_end() -> None:
    day = date(2026, 10, 15)
    assert covers(None, None, day)
    assert covers(day, None, day)
    assert not covers(day + timedelta(days=1), None, day)
    assert not covers(None, day, day)
    assert covers(None, day + timedelta(days=1), day)
    assert covers(day - timedelta(days=1), day + timedelta(days=1), day)


def test_an_old_edition_stays_addressable_and_two_current_editions_are_not_chosen(client: TestClient) -> None:
    with get_sessionmaker()() as db:
        book = _biology(db)
        original = str(book.id)
        edition_id: uuid.UUID | None = None
        source_id: uuid.UUID | None = None
        try:
            today = _today(db)
            book.effective_until = today
            db.commit()
            assert client.get("/v1/grades/11/subjects/biology/book").status_code == 404
            book.effective_from = None
            book.effective_until = None
            db.commit()

            edition, source = _fixture_edition(db, book, start=today - timedelta(days=30), end=today)
            edition_id, source_id = edition.id, source.id
            current = client.get("/v1/grades/11/subjects/biology/book")
            assert current.status_code == 200 and current.json()["chapters"]
            old = client.get(f"/v1/books/{edition.id}")
            assert old.status_code == 200 and old.json()["edition"] == "fixture" and old.json()["chapters"] == []
            listed = client.get("/v1/discovery").json()
            assert str(edition.id) not in {b["book_id"] for b in listed["books"]}
            catalogue = client.get("/v1/catalogue").json()
            biology = next(
                s
                for g in catalogue["grades"]
                if g["grade"]["number"] == 11
                for s in g["subjects"]
                if s["subject"]["code"] == "biology"
            )
            assert [b["id"] for b in biology["books"]] == [original]

            edition.effective_from = None
            edition.effective_until = None
            db.commit()
            overlap = client.get("/v1/grades/11/subjects/biology/book")
            assert overlap.status_code == 409
            assert "none is chosen" in overlap.json()["detail"]
        finally:
            db.rollback()
            book = db.get(BookEdition, uuid.UUID(original))
            assert book is not None
            book.effective_from = None
            book.effective_until = None
            if edition_id is not None:
                db.execute(delete(BookEdition).where(BookEdition.id == edition_id))
            if source_id is not None:
                db.execute(delete(SourceDocument).where(SourceDocument.id == source_id))
            db.commit()


def _today(db: Session) -> date:
    from sqlalchemy import func

    return local_date(db.execute(select(func.now())).scalar_one())


def _biology(db: Session) -> BookEdition:
    book = db.scalars(
        select(BookEdition)
        .join(Grade, BookEdition.grade_id == Grade.id)
        .join(Subject, BookEdition.subject_id == Subject.id)
        .where(Grade.number == 11, Subject.code == "biology")
    ).one()
    return book


def _fixture_edition(db: Session, book: BookEdition, *, start: date, end: date) -> tuple[BookEdition, SourceDocument]:
    src = book.source
    source = SourceDocument(
        id=uuid.uuid4(),
        source_id="FIXTURE-EDITION-WINDOW",
        grade_number=src.grade_number,
        subject_code=src.subject_code,
        title="Technical fixture edition",
        authority=src.authority,
        edition="fixture",
        file_path=src.file_path,
        sha256=src.sha256,
        bytes=src.bytes,
        pdf_pages=src.pdf_pages,
        page_rule=src.page_rule,
        completeness=src.completeness,
        missing_pages=list(src.missing_pages or []),
        duplicate_pages=list(src.duplicate_pages or []),
        rights=src.rights,
        status=src.status,
        metadata_json={"fixture": True},
        publication_rights="UNVERIFIED",
    )
    edition = BookEdition(
        id=uuid.uuid4(),
        natural_key="fixture-edition-window",
        grade_id=book.grade_id,
        subject_id=book.subject_id,
        source_document_id=source.id,
        title="Technical fixture edition",
        chapter_label=book.chapter_label,
        effective_from=start,
        effective_until=end,
    )
    db.add(source)
    db.add(edition)
    db.commit()
    return edition, source
