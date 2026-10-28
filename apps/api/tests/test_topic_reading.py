"""A topic opens one lesson. Draft text stays with staff who cover that class and subject (TOPIC-READER-01)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.curriculum.models import Topic
from tests.test_content_workflow import FIXTURE_BODY, Staff, _chapter, _refs, _save


def test_a_draft_is_not_a_learner_lesson_and_two_drafts_are_not_picked(client: TestClient) -> None:
    with get_sessionmaker()() as db:
        chapter, doc = _chapter(db, 11, "biology")
        topic = db.scalars(
            select(Topic)
            .where(Topic.chapter_id == chapter.id, Topic.parent_id.is_(None), Topic.retired_at.is_(None))
            .order_by(Topic.display_order)
        ).first()
        assert topic is not None
        topic_id = str(topic.id)
        refs = _refs(chapter, doc)
        scope = {"grades": [11], "subjects": ["biology"]}
        author = Staff(client, db, ["content_author"], scope)
        owner = Staff(client, db, ["owner_admin"], scope)
        outsider = Staff(client, db, ["content_author"], {"grades": [11], "subjects": ["chemistry"]})
        learner = Staff(client, db, [])

    created = client.post(
        "/v1/studio/items",
        headers=author.headers,
        json={"chapter_id": str(chapter.id), "topic_id": topic_id, "title": "Fixture topic lesson"},
    )
    assert created.status_code == 201, created.text
    item = created.json()
    saved = _save(client, author, item, FIXTURE_BODY, refs)
    assert saved.status_code == 200, saved.text

    path = f"/v1/topics/{topic_id}/lesson"
    for who in (None, learner, outsider):
        headers = {} if who is None else who.headers
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["availability"] == "unavailable" and body["lesson"] is None
        assert "Fixture" not in response.text

    shown = client.get(path, headers=author.headers)
    assert shown.status_code == 200, shown.text
    preview = shown.json()
    # CHAPTER-OPENING-01: the chapter's first topic opens the chapter; the one after it does not.
    assert preview["chapter_start"] is True and preview["previous_topic_id"] is None
    after = client.get(f"/v1/topics/{preview['next_topic_id']}/lesson").json()
    assert after["chapter_start"] is False
    assert preview["availability"] == "private_preview"
    assert preview["lesson"]["private_preview"] is True
    assert preview["lesson"]["status"] == "draft"
    assert "Technical fixture paragraph" in response_text(preview)
    assert preview["lesson"]["source_refs"]

    owner_view = client.get(path, headers=owner.headers)
    assert owner_view.status_code == 200 and owner_view.json()["availability"] == "private_preview"

    missing = client.get(f"{path}?language=ur", headers=author.headers)
    assert missing.status_code == 200
    assert missing.json()["lesson"]["requested_language_missing"] is True
    assert missing.json()["lesson"]["language"] == "en"
    assert missing.json()["lesson"]["available_languages"] == ["en"]

    second = client.post(
        "/v1/studio/items",
        headers=author.headers,
        json={"chapter_id": str(chapter.id), "topic_id": topic_id, "title": "Fixture second lesson"},
    )
    assert second.status_code == 201, second.text
    assert _save(client, author, second.json(), FIXTURE_BODY, refs).status_code == 200
    conflict = client.get(path, headers=author.headers)
    assert conflict.status_code == 409
    hidden = client.get(path)
    assert hidden.status_code == 200 and hidden.json()["lesson"] is None


def response_text(payload: dict) -> str:
    return str(payload["lesson"]["body"])


def test_next_and_previous_follow_the_books_reading_order(client: TestClient) -> None:
    # A topic is followed by its subtopics, depth first, then by the next topic (1.2, 1.2.1, 1.2.2, 1.2.2.1, …, 1.3);
    # siblings alone skipped every subtopic (owner, 2026-10-28).
    with get_sessionmaker()() as db:
        live = [t for t in db.scalars(select(Topic).where(Topic.retired_at.is_(None))) if t.parent_id is not None]
        by_parent: dict = {}
        for t in live:
            by_parent.setdefault(t.parent_id, []).append(t)
        top = next(
            t
            for t in db.scalars(
                select(Topic).where(Topic.parent_id.is_(None), Topic.retired_at.is_(None)).order_by(Topic.display_order)
            )
            if t.id in by_parent
        )
        first_child = min(by_parent[top.id], key=lambda t: (t.display_order, t.id))
        siblings = sorted(
            db.scalars(
                select(Topic).where(
                    Topic.chapter_id == top.chapter_id, Topic.parent_id.is_(None), Topic.retired_at.is_(None)
                )
            ),
            key=lambda t: (t.display_order, t.id),
        )
        after = siblings[siblings.index(top) + 1] if siblings.index(top) + 1 < len(siblings) else None

        def last_descendant(t: Topic) -> Topic:
            kids = sorted(by_parent.get(t.id, []), key=lambda k: (k.display_order, k.id))
            return last_descendant(kids[-1]) if kids else t

        last = last_descendant(top)

    reading = client.get(f"/v1/topics/{top.id}/lesson").json()
    assert reading["next_topic_id"] == str(first_child.id)
    child = client.get(f"/v1/topics/{first_child.id}/lesson").json()
    assert child["previous_topic_id"] == str(top.id) and child["chapter_start"] is False
    end = client.get(f"/v1/topics/{last.id}/lesson").json()
    assert end["next_topic_id"] == (str(after.id) if after else None)
