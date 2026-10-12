"""W07.S2.T1 (NEXT-STEPS-01): targeted next steps on a released written result.

For a scored question that lost marks, the learner sees the rubric's own approved wording for each criterion that
didn't earn full credit (with its listed common mistakes), and live lessons for the question's topic or chapter, or
an honest note that none is published yet. Nothing is generated. An alternative route the learner didn't take isn't
listed once another route earned credit. Scripts, rubrics and lessons are technical fixtures.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _create, _post, _refs, _save
from tests.test_written_attempts import _learner, _map, _png, _seal, _start, _upload
from tests.test_written_marking import _case_for, _decide, _reviewer


def _released(client: TestClient, chapter: str, awards: dict[str, Any]) -> dict[str, Any]:
    learner = _learner(client)
    a = _start(client, learner, chapter)
    page = _upload(client, learner, a["id"], _png(seed=int(uuid.uuid4().int % 250))).json()["pages"][0]["id"]
    m = _map(client, learner, a, {"1:a": {"pages": [page]}, "1:b": {"pages": [page]}}).json()
    assert _seal(client, learner, a["id"], m["manifest_revision"]).status_code == 200
    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, a["id"])
    client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)
    assert _decide(client, reviewer, case["id"], 0, awards, release=True).status_code == 200
    result = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
    return dict(result["questions"][0])


def _units(a1: int, b1: int, b2: int) -> dict[str, Any]:
    return {"1": {"a1": {"units": a1}, "b1": {"units": b1}, "b2": {"units": b2}}}


def _publish_lesson(client: TestClient) -> str:
    scope = {"grades": [12], "subjects": ["chemistry"]}
    with get_sessionmaker()() as db:
        author = Staff(client, db, ["content_author"], scope)
        reviewer = Staff(client, db, ["subject_reviewer"], scope)
        publisher = Staff(client, db, ["publisher"], scope, mfa=True)
        chapter, doc = _chapter(db, 12, "chemistry", 2)  # the written fixture's chapter
        _confirm_rights(client, db, doc)
    item = _create(client, author, chapter, title="Fixture next-step lesson")
    body = {"blocks": [{"type": "paragraph", "text": "Technical fixture lesson text, not academic content."}]}
    assert _save(client, author, item, body=body, refs=_refs(chapter, doc)).status_code == 200
    assert _post(client, author, item["id"], "submit", {"note": "ready"}).status_code == 200
    review = {"decision": "approve", "comment": "Checked fixture"}
    assert _post(client, reviewer, item["id"], "review", review).status_code == 200
    assert _post(client, publisher, item["id"], "publish").status_code == 200
    return str(item["id"])


def test_next_steps_use_the_rubrics_words_and_live_lessons(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    chapter = published_written["chapter"]
    lost = _released(client, chapter, _units(100, 0, 0))
    steps = lost["next_steps"]
    assert [(f["criterion_id"], f["description"]) for f in steps["focus"]] == [
        ("a1", "Fixture criterion a1"),
        ("b1", "Fixture method one"),
        ("b2", "Fixture method two"),
    ]
    assert all(f["common_mistakes"] == [] for f in steps["focus"])  # the fixture rubric lists none
    assert steps["chapter_id"] == chapter
    if not steps["lessons"]:
        assert steps["lessons_missing"] is True  # said plainly, never filled in

    # Full marks: nothing to suggest.
    assert _released(client, chapter, _units(200, 300, 0))["next_steps"] is None
    # Route b1 earned credit, so the untaken route b2 isn't suggested.
    partial = _released(client, chapter, _units(200, 150, 0))["next_steps"]
    assert [f["criterion_id"] for f in partial["focus"]] == ["b1"]

    # A live lesson in the question's chapter is offered.
    lesson = _publish_lesson(client)
    linked = _released(client, chapter, _units(100, 0, 0))["next_steps"]
    assert lesson in [x["id"] for x in linked["lessons"]] and linked["lessons_missing"] is False
