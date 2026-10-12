"""P05.S4.T2 (REGION-01): another region's records exist without becoming discoverable.

A labelled technical second region (one Class XI Physics book with a chapter and a topic) is committed for this test
only and removed afterwards; no other province's academic catalogue is created. Learners still see only Punjab:
the catalogue, the book, chapter and lesson pages, search, offline packs and the practice and pattern builders
ignore it. Before this fix the catalogue listed every region's classes.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment import forms, profiles
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Region, SourceDocument, Subject, Topic
from tests.test_attempts import _learner


def _second_region(tag: str) -> dict[str, uuid.UUID]:
    with get_sessionmaker()() as s:
        physics = s.scalar(select(Subject.id).where(Subject.code == "physics"))
        ids = {k: uuid.uuid4() for k in ("region", "grade", "source", "book", "chapter", "topic")}
        s.add(Region(id=ids["region"], code=f"fixture-region-{tag}", name="Fixture region (technical)"))
        s.flush()
        s.add(
            Grade(id=ids["grade"], region_id=ids["region"], number=11, code=f"FX{tag[:5]}", name="Class XI (fixture)")
        )
        s.add(
            SourceDocument(
                id=ids["source"],
                source_id=f"FIXTURE-REGION-{tag}",
                grade_number=11,
                subject_code="physics",
                title="Fixture: technical book in another region",
                file_path="fixture/none.pdf",
                sha256="0" * 64,
                bytes=0,
                pdf_pages=0,
                completeness="complete",
                rights="Fixture: technical record only",
                status="fixture",
            )
        )
        s.flush()
        s.add(
            BookEdition(
                id=ids["book"],
                natural_key=f"fixture-region-book-{tag}",
                grade_id=ids["grade"],
                subject_id=physics,
                source_document_id=ids["source"],
                title="Fixture: technical book in another region",
                chapter_label="Chapter",
            )
        )
        s.flush()
        s.add(
            Chapter(
                id=ids["chapter"],
                natural_key=f"fixture-region-ch-{tag}",
                book_id=ids["book"],
                display_order=1,
                number=1,
                title=f"Zyxwv fixture region chapter {tag}",
                status="complete",
            )
        )
        s.flush()
        s.add(
            Topic(
                id=ids["topic"],
                natural_key=f"fixture-region-topic-{tag}",
                chapter_id=ids["chapter"],
                display_order=1,
                title=f"Zyxwv fixture region topic {tag}",
                depth=1,
            )
        )
        s.commit()
    return ids


def _remove(ids: dict[str, uuid.UUID]) -> None:
    with get_sessionmaker()() as s:
        s.execute(delete(Topic).where(Topic.id == ids["topic"]))
        s.execute(delete(Chapter).where(Chapter.id == ids["chapter"]))
        s.execute(delete(BookEdition).where(BookEdition.id == ids["book"]))
        s.execute(delete(SourceDocument).where(SourceDocument.id == ids["source"]))
        s.execute(delete(Grade).where(Grade.id == ids["grade"]))
        s.execute(delete(Region).where(Region.id == ids["region"]))
        s.commit()


def test_another_region_is_never_discoverable(client: TestClient, physics: dict[str, Any]) -> None:
    before = client.get("/v1/catalogue").json()
    tag = uuid.uuid4().hex[:8]
    ids = _second_region(tag)
    try:
        catalogue = client.get("/v1/catalogue").json()
        assert [g["grade"]["number"] for g in catalogue["grades"]] == [g["grade"]["number"] for g in before["grades"]]
        assert str(ids["book"]) not in str(catalogue) and catalogue["region"] == "pk-punjab"
        assert client.get(f"/v1/books/{ids['book']}").status_code == 404
        assert client.get(f"/v1/chapters/{ids['chapter']}").status_code == 404
        assert client.get(f"/v1/chapters/{ids['chapter']}/lessons").status_code == 404
        punjab_book = client.get("/v1/grades/11/subjects/physics/book")
        assert punjab_book.status_code == 200 and str(ids["book"]) not in punjab_book.text
        found = client.get("/v1/search", params={"q": f"Zyxwv fixture region {tag}"}).json()
        assert found["hits"] == []

        learner = _learner(client)
        assert client.get(f"/v1/me/study-packs/{ids['chapter']}", headers=learner.headers).status_code == 404
        refused = client.post(
            "/v1/practice/forms",
            headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex},
            json={"grade": 11, "subject": "physics", "chapter_ids": [str(ids["chapter"])], "question_count": 1},
        )
        assert refused.status_code == 422
        with get_sessionmaker()() as db:
            assert ids["chapter"] not in {c.id for c in forms._book_chapters(db, 11, "physics")}
            # A pattern's section still resolves to the one released edition: no conflict from the other region.
            assert profiles.catalogue_problems(db, [{"subject": "physics", "grades": [11], "questions": 1}]) == []
        # The practice builder still works on Punjab's own book.
        ok = client.post(
            "/v1/practice/forms",
            headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex},
            json={"grade": 11, "subject": "physics", "chapter_ids": [physics["chapter"]], "question_count": 1},
        )
        assert ok.status_code == 201, ok.text
    finally:
        _remove(ids)
