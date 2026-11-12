"""Book mistakes: a book's printed errors and their corrections, by chapter and topic (BOOK-MISTAKES-01)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.content.book_mistakes import mistakes_in
from portal_api.modules.curriculum.models import Topic
from tests.test_content_workflow import Staff, _chapter, _refs, _save

MARKED = {"type": "paragraph", "text": "The fixture unit is printed as mu.", "book_errors": ["mu"]}
FIGURE = {"type": "paragraph", "text": "A fixture figure, wrong as a whole."}
FIX = {"type": "callout", "tone": "correction", "title": "Book correction", "text": "The fixture unit is u."}
FIX2 = {"type": "callout", "tone": "correction", "title": "Book correction", "text": "And its label is u too."}
PLAIN = {"type": "paragraph", "text": "Fixture text with no error."}


def test_each_correction_takes_the_marked_passage_or_the_block_before_it() -> None:
    note = {"type": "callout", "tone": "note", "text": "x"}
    found = mistakes_in([PLAIN, MARKED, PLAIN, FIX, FIGURE, FIX, FIX2, note])
    assert [(m.context, m.corrections) for m in found] == [([MARKED], [FIX]), ([FIGURE], [FIX, FIX2])]
    assert mistakes_in([PLAIN, MARKED]) == []  # marks without a correction box are not a listed mistake
    assert mistakes_in([FIX])[0].context == []  # a box at the very start has nothing printed before it
    assert mistakes_in(["junk", None, FIX])[0].corrections == [FIX]


def test_a_figure_printed_with_the_passage_comes_with_it() -> None:
    chart = {"type": "diagram", "$asset": "fixture-chart", "alt": "A fixture chart."}
    side = {**chart, "side": True}
    # A figure between the marked passage and its boxes (the book prints it there) belongs to the mistake.
    assert mistakes_in([MARKED, chart, FIX, FIX2])[0].context == [MARKED, chart]
    # A side figure is printed before its text; with nothing marked it comes with the block before the box.
    assert mistakes_in([side, PLAIN, FIGURE, FIX])[0].context == [side, FIGURE]
    # A figure that is not at the side stays out unless it is the block just before the box.
    assert mistakes_in([chart, PLAIN, FIGURE, FIX])[0].context == [FIGURE]


def test_drafts_show_to_staff_in_scope_and_the_summary_carries_no_text(client: TestClient) -> None:
    with get_sessionmaker()() as db:
        chapter, doc = _chapter(db, 12, "physics", index=-1)
        topic = db.scalars(
            select(Topic)
            .where(Topic.chapter_id == chapter.id, Topic.retired_at.is_(None))
            .order_by(Topic.display_order.desc())
        ).first()
        assert topic is not None
        chapter_id, topic_id, refs = str(chapter.id), str(topic.id), _refs(chapter, doc)
        author = Staff(client, db, ["content_author"], {"grades": [12], "subjects": ["physics"]})
        outsider = Staff(client, db, ["content_author"], {"grades": [12], "subjects": ["chemistry"]})
        learner = Staff(client, db, [])

    created = client.post(
        "/v1/studio/items",
        headers=author.headers,
        json={"chapter_id": chapter_id, "topic_id": topic_id, "title": "Fixture book-mistake lesson"},
    )
    assert created.status_code == 201, created.text
    saved = _save(client, author, created.json(), {"blocks": [PLAIN, MARKED, FIX, FIGURE, FIX, FIX2]}, refs)
    assert saved.status_code == 200, saved.text

    summary_path = "/v1/grades/12/subjects/physics/book-mistakes"
    chapter_path = f"/v1/chapters/{chapter_id}/book-mistakes"
    for who in (None, learner, outsider):  # a draft is nobody's lesson but staff in scope
        headers = {} if who is None else who.headers
        for path in (summary_path, chapter_path):
            response = client.get(path, headers=headers)
            assert response.status_code == 200, response.text
            assert topic_id not in response.text and "Fixture" not in response.text

    summary = client.get(summary_path, headers=author.headers)
    assert summary.status_code == 200 and summary.headers["cache-control"] == "private, no-store"
    listed = next(c for c in summary.json()["chapters"] if c["chapter_id"] == chapter_id)
    row = next(t for t in listed["topics"] if t["topic_id"] == topic_id)
    assert row["count"] == 2 and row["availability"] == "private_preview" and row["mistakes"] == []
    assert "fixture unit" not in summary.text.lower()  # counts only

    detail = client.get(chapter_path, headers=author.headers).json()
    assert [c["chapter_id"] for c in detail["chapters"]] == [chapter_id]
    row = next(t for t in detail["chapters"][0]["topics"] if t["topic_id"] == topic_id)

    def plain(blocks: list[dict[str, object]]) -> list[dict[str, object]]:
        return [{k: v for k, v in b.items() if k != "v"} for b in blocks]  # stored blocks carry their schema version

    assert [plain(m["context"]) for m in row["mistakes"]] == [[MARKED], [FIGURE]]
    assert [plain(m["corrections"]) for m in row["mistakes"]] == [[FIX], [FIX, FIX2]]

    assert client.get("/v1/chapters/00000000-0000-0000-0000-000000000000/book-mistakes").status_code == 404
    assert client.get("/v1/grades/11/subjects/english/book-mistakes").status_code == 404
