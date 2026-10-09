"""P16.S3.T3 (ACADEMIC-UPDATES-01): source review dates and syllabus notices that wait for human review."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_content_workflow import Staff, _chapter

SCOPE = {"grades": [11], "subjects": ["chemistry"]}


def test_source_reviews_clear_the_stale_flag_and_need_a_scoped_reviewer(client: TestClient, db: Session) -> None:
    _, doc = _chapter(db, 11, "chemistry")
    reviewer, author = Staff(client, db, ["subject_reviewer"], SCOPE), Staff(client, db, ["content_author"], SCOPE)
    url = f"/v1/studio/sources/{doc.id}/review"
    assert client.post(url, headers=author.headers, json={"note": "Fixture: checked edition"}).status_code == 403
    other = Staff(client, db, ["subject_reviewer"], {"grades": [12], "subjects": ["chemistry"]})
    assert client.post(url, headers=other.headers, json={"note": "Fixture: checked edition"}).status_code == 403
    assert client.post(url, headers=reviewer.headers, json={"note": "Fixture: checked edition"}).status_code == 204
    rows = client.get("/v1/studio/sources", headers=reviewer.headers).json()
    mine = next(r for r in rows if r["id"] == str(doc.id))
    assert mine["last_reviewed_at"] and mine["review_stale"] is False


def test_notices_wait_for_a_reviewer_and_change_nothing_by_themselves(client: TestClient, db: Session) -> None:
    author, reviewer = Staff(client, db, ["content_author"], SCOPE), Staff(client, db, ["subject_reviewer"], SCOPE)
    body = {
        "grade": 11,
        "subject": "chemistry",
        "title": "Fixture syllabus notice",
        "source_url": "https://example.invalid/notice",
        "summary": "Fixture: a chapter order change was announced.",
    }
    logged = client.post("/v1/studio/syllabus-notices", headers=author.headers, json=body)
    assert logged.status_code == 201, logged.text
    notice = next(n for n in logged.json() if n["title"] == "Fixture syllabus notice" and n["status"] == "open")
    assert notice["can_decide"] is False
    bad = {**body, "grade": 12}
    assert client.post("/v1/studio/syllabus-notices", headers=author.headers, json=bad).status_code == 403
    url = f"/v1/studio/syllabus-notices/{notice['id']}/decision"
    decision = {"accept": True, "decision": "Fixture: plan revisions for chapter 3"}
    assert client.post(url, headers=author.headers, json=decision).status_code == 403
    done = client.post(url, headers=reviewer.headers, json=decision)
    assert done.status_code == 200
    assert next(n for n in done.json() if n["id"] == notice["id"])["status"] == "accepted"
    assert client.post(url, headers=reviewer.headers, json=decision).status_code == 409
