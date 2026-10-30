"""A topic opens one lesson. Draft text stays with staff who cover that class and subject (TOPIC-READER-01)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, SourceDocument, Subject, Topic
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


def _exercise_topics(db: Session, grade: int, subject: str) -> list[Topic]:
    return list(
        db.scalars(
            select(Topic)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(BookEdition, BookEdition.id == Chapter.book_id)
            .join(Grade, Grade.id == BookEdition.grade_id)
            .join(Subject, Subject.id == BookEdition.subject_id)
            .where(
                Grade.number == grade,
                Subject.code == subject,
                Topic.retired_at.is_(None),
                Topic.natural_key.endswith("/u-exercise"),
            )
            .order_by(Chapter.display_order)
        )
    )


def test_the_end_of_chapter_exercise_is_practice_not_learn(client: TestClient) -> None:
    # BOOK-EXERCISES-01: the outline marks the exercise, Learn's next/previous never lead into it; it still reads by id.
    with get_sessionmaker()() as db:
        exercise = _exercise_topics(db, 11, "computer_science")[0]
        assert exercise.kind == "exercise"
        chapter_id, exercise_id = str(exercise.chapter_id), str(exercise.id)

    chapter = client.get(f"/v1/chapters/{chapter_id}").json()
    kinds = {t["id"]: t["kind"] for t in chapter["topics"]}
    assert kinds[exercise_id] == "exercise"
    assert [k for k in kinds.values() if k == "exercise"] == ["exercise"]

    ids: list[str] = []
    topic_id: str | None = next(t["id"] for t in chapter["topics"] if t["kind"] == "topic")
    while topic_id:  # walk the whole chapter the way the reader's "Next topic" does
        ids.append(topic_id)
        reading = client.get(f"/v1/topics/{topic_id}/lesson").json()
        assert reading["kind"] == "topic"
        topic_id = reading["next_topic_id"]
    assert exercise_id not in ids and len(ids) > 1
    last = client.get(f"/v1/topics/{ids[-1]}/lesson").json()
    assert last["next_topic_id"] is None

    shown = client.get(f"/v1/topics/{exercise_id}/lesson")
    assert shown.status_code == 200, shown.text
    body = shown.json()
    assert body["kind"] == "exercise" and body["title"] == "Exercise"
    assert body["previous_topic_id"] is None and body["next_topic_id"] is None and body["chapter_start"] is False


def test_practice_lists_each_chapters_exercise_with_what_the_caller_can_read(client: TestClient) -> None:
    with get_sessionmaker()() as db:
        topics = _exercise_topics(db, 12, "computer_science")
        target = topics[-1]
        chapter = db.get(Chapter, target.chapter_id)
        assert chapter is not None
        book = db.get(BookEdition, chapter.book_id)
        assert book is not None
        doc = db.get(SourceDocument, book.source_document_id)
        assert doc is not None
        refs = _refs(chapter, doc)
        scope = {"grades": [12], "subjects": ["computer_science"]}
        author = Staff(client, db, ["content_author"], scope)
        expected = [str(t.id) for t in topics]
        target_id, chapter_id = str(target.id), str(chapter.id)

    path = "/v1/grades/12/subjects/computer_science/exercises"
    listed = client.get(path)
    assert listed.status_code == 200, listed.text
    assert listed.headers["cache-control"] == "private, no-store"
    body = listed.json()
    assert body["grade_number"] == 12 and body["subject_code"] == "computer_science"
    assert [e["topic_id"] for e in body["exercises"]] == expected
    numbers = [e["chapter_number"] for e in body["exercises"]]
    assert numbers == sorted(numbers)
    assert all(e["availability"] == "unavailable" and e["available_languages"] == [] for e in body["exercises"])

    created = client.post(
        "/v1/studio/items",
        headers=author.headers,
        json={"chapter_id": chapter_id, "topic_id": target_id, "title": "Fixture exercise lesson"},
    )
    assert created.status_code == 201, created.text
    assert _save(client, author, created.json(), FIXTURE_BODY, refs).status_code == 200

    staff = {e["topic_id"]: e for e in client.get(path, headers=author.headers).json()["exercises"]}
    assert staff[target_id]["availability"] == "private_preview"
    assert staff[target_id]["available_languages"] == ["en"]
    learner = {e["topic_id"]: e for e in client.get(path).json()["exercises"]}
    assert learner[target_id]["availability"] == "unavailable"

    # Another class's book is never mixed in.
    assert not set(expected) & {
        e["topic_id"] for e in client.get("/v1/grades/11/subjects/computer_science/exercises").json()["exercises"]
    }
    assert client.get("/v1/grades/11/subjects/english/exercises").status_code == 404


def test_the_topic_kind_rule_is_the_catalogue_key() -> None:
    # BOOK-PAPERS-01: the Board papers at the end of a book are a third, Practice-only kind.
    cs12 = "pk-punjab/xii/computer_science/c12-cs/ch9"
    kinds = {
        key: (Topic(natural_key=f"{cs12}/{key}").kind, Topic(natural_key=f"{cs12}/{key}").practice_only)
        for key in ("9.1", "u-business-plan-tools", "u-exercise", "u-paper-pattern", "u-model-paper", "u-paper")
    }
    assert kinds == {
        "9.1": ("topic", False),
        "u-business-plan-tools": ("topic", False),
        "u-exercise": ("exercise", True),
        "u-paper-pattern": ("paper", True),
        "u-model-paper": ("paper", True),
        "u-paper": ("topic", False),
    }


PAPERS = (("u-paper-pattern", "Paper Pattern"), ("u-model-paper", "Model Paper"))


def test_the_board_papers_are_practice_not_learn(client: TestClient) -> None:
    # BOOK-PAPERS-01: the content adds the two papers to Computer Science 12's last unit. A catalogue that doesn't have
    # them yet gets them after the unit's last topic for this test only; ones already there are used as they are.
    with get_sessionmaker()() as db:
        book = db.scalars(
            select(BookEdition)
            .join(Grade, Grade.id == BookEdition.grade_id)
            .join(Subject, Subject.id == BookEdition.subject_id)
            .where(Grade.number == 12, Subject.code == "computer_science")
        ).one()
        chapter = db.scalars(
            select(Chapter)
            .where(Chapter.book_id == book.id, Chapter.retired_at.is_(None))
            .order_by(Chapter.display_order.desc())
        ).first()
        assert chapter is not None
        live = [t for t in chapter.topics if t.retired_at is None]
        by_key = {t.natural_key: t for t in live}
        last = max(t.display_order for t in live)
        papers: list[Topic] = []
        added: list[Topic] = []
        for n, (key, title) in enumerate(PAPERS, 1):
            topic = by_key.get(f"{chapter.natural_key}/{key}")
            if topic is None:
                topic = Topic(
                    id=uuid.uuid4(),
                    natural_key=f"{chapter.natural_key}/{key}",
                    chapter_id=chapter.id,
                    display_order=last + n,
                    title=title,
                    depth=1,
                    points=[],
                )
                added.append(topic)
            papers.append(topic)
        db.add_all(added)
        db.commit()
        chapter_id = str(chapter.id)
        paper_ids = [str(t.id) for t in papers]
        added_ids = [str(t.id) for t in added]
        first_id = str(next(t.id for t in sorted(live, key=lambda t: t.display_order) if t.kind == "topic"))

    try:
        outline = client.get(f"/v1/chapters/{chapter_id}").json()
        kinds = {t["id"]: t["kind"] for t in outline["topics"]}
        assert [kinds[i] for i in paper_ids] == ["paper", "paper"]

        ids: list[str] = []
        topic_id: str | None = first_id
        while topic_id:  # Learn's "Next topic" walks the unit and never reaches a paper
            ids.append(topic_id)
            reading = client.get(f"/v1/topics/{topic_id}/lesson").json()
            assert reading["kind"] == "topic"
            topic_id = reading["next_topic_id"]
        assert not set(paper_ids) & set(ids) and len(ids) > 1

        for paper_id, title in zip(paper_ids, [title for _key, title in PAPERS], strict=True):
            body = client.get(f"/v1/topics/{paper_id}/lesson").json()
            assert body["kind"] == "paper" and body["title"] == title
            assert body["previous_topic_id"] is None and body["next_topic_id"] is None
            assert body["chapter_start"] is False

        listed = client.get("/v1/grades/12/subjects/computer_science/exercises").json()
        assert [(p["topic_id"], p["title"]) for p in listed["papers"]] == list(
            zip(paper_ids, [title for _key, title in PAPERS], strict=True)
        )
        assert all(p["availability"] == "unavailable" and p["available_languages"] == [] for p in listed["papers"])
        assert not set(paper_ids) & {e["topic_id"] for e in listed["exercises"]}
        # Class 11 and Class 12 are never mixed: the Class 11 book lists no Class 12 paper.
        other = client.get("/v1/grades/11/subjects/computer_science/exercises").json()
        assert not set(paper_ids) & {p["topic_id"] for p in other["papers"]}
        assert client.get("/v1/grades/12/subjects/biology/exercises").json()["papers"] == []
    finally:
        with get_sessionmaker()() as db:
            for paper_id in added_ids:
                db.delete(db.get(Topic, uuid.UUID(paper_id)))
            db.commit()
