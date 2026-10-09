"""P09.S1.T2: half-book, full-book and XI+XII combined practice scopes, defined by the book's chapter order."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment.forms import _book_chapters
from tests.test_attempts import POOL, _learner


def _form(client: TestClient, who: Any, **body: Any) -> Any:
    return client.post(
        "/v1/practice/forms",
        headers={**who.headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"grade": 11, "subject": "physics", "question_count": POOL, **body},
    )


def test_book_scopes_follow_the_books_chapter_order(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    with get_sessionmaker()() as db:
        xi = [str(c.id) for c in _book_chapters(db, 11, "physics")]
        xii = [str(c.id) for c in _book_chapters(db, 12, "physics")]
    full = _form(client, who, scope="full_book")
    assert full.status_code == 201, full.text
    assert full.json()["scope"]["mode"] == "full_book" and full.json()["scope"]["chapter_ids"] == sorted(xi)
    first = _form(client, who, scope="half_book", half=1)
    assert first.status_code == 201, first.text  # the fixture chapter is the book's first chapter
    split = (len(xi) + 1) // 2
    assert first.json()["scope"]["chapter_ids"] == sorted(xi[:split])
    second = _form(client, who, scope="half_book", half=2)
    if second.status_code == 201:
        assert second.json()["scope"]["chapter_ids"] == sorted(xi[split:])
    else:  # honest shortage: no approved questions in the second half of the fixture book
        assert second.status_code == 422 and "available" in second.json()
    combined = _form(client, who, scope="combined")
    assert combined.status_code == 201, combined.text
    assert combined.json()["scope"]["grades"] == [11, 12]
    assert combined.json()["scope"]["chapter_ids"] == sorted(xi + xii)


def test_scope_rules(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    assert _form(client, who, scope="half_book").status_code == 422  # which half?
    assert _form(client, who, scope="full_book", topic_ids=[str(uuid.uuid4())]).status_code == 422
    assert _form(client, who).status_code == 422  # a chapter test needs chapters
