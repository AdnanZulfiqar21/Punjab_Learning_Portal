"""P12.S1.T2 (REVIEW-LINKS-01): each reviewed question links to the published lessons for its topic (or chapter, when
it has no topic), so a learner can go straight from a mistake to the teaching. Only live lessons are linked. Technical
fixture questions and lessons only."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests import test_content_workflow
from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _create, _post, _refs, _save
from tests.test_mistake_notebook import _answer, _submit

team = test_content_workflow.team


def test_reviewed_questions_link_to_live_lessons_for_their_chapter(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct={1})
    _submit(client, learner, attempt["id"])
    result = client.get(f"/v1/attempts/{attempt['id']}/result", headers=learner.headers).json()
    assert all("related_lessons" in i for i in result["items"])
    before = {x["id"] for i in result["items"] for x in i["related_lessons"]}

    # Publish a lesson in the questions' chapter (physics fixture chapter), then the review links to it.
    chapter, doc = _chapter(db, 11, "physics")
    scope = {"grades": [11], "subjects": ["physics"]}
    author = Staff(client, db, ["content_author"], scope)
    reviewer = Staff(client, db, ["subject_reviewer"], scope)
    publisher = Staff(client, db, ["publisher"], scope, mfa=True)
    _confirm_rights(client, db, doc)
    lesson = _create(client, author, chapter)
    assert _save(client, author, lesson, refs=_refs(chapter, doc)).status_code == 200
    assert _post(client, author, lesson["id"], "submit", {"note": "ready"}).status_code == 200
    assert (
        _post(client, reviewer, lesson["id"], "review", {"decision": "approve", "comment": "Fixture"}).status_code
        == 200
    )
    draft = _create(client, author, chapter)  # an unpublished lesson is never linked
    assert _post(client, publisher, lesson["id"], "publish").status_code == 200

    after = client.get(f"/v1/attempts/{attempt['id']}/result", headers=learner.headers).json()
    for item in after["items"]:
        ids = {x["id"] for x in item["related_lessons"]}
        assert lesson["id"] in ids and draft["id"] not in ids
        assert all({"id", "title", "chapter_id"} <= set(x) for x in item["related_lessons"])
    assert lesson["id"] not in before
    assert team is not None
