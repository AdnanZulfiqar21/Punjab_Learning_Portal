"""P05.S1.T2 (CONCEPTS-01): canonical learning concepts (outcomes) with prerequisites. One concept is written once and
mapped to the topics that teach it in any edition or course, never duplicated. Prerequisites form an acyclic graph; a
prerequisite may name an introductory bridging lesson. Concepts are staff-authored academic content: published only
after an independent reviewer approves them with source references. Technical fixture concepts only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.modules.curriculum.models import Topic
from tests.test_content_workflow import Staff, _chapter

BIO_BOTH = {"grades": [11, 12], "subjects": ["biology"]}
URL = "/v1/studio/concepts"


def _topics(db: Session, grade: int, subject: str = "biology", index: int = 0, n: int = 2) -> list[str]:
    chapter, _ = _chapter(db, grade, subject, index)
    rows = db.scalars(select(Topic.id).where(Topic.chapter_id == chapter.id, Topic.retired_at.is_(None)).limit(n))
    return [str(t) for t in rows]


def _concept(client: TestClient, who: Staff, code: str | None = None, **extra: Any) -> dict[str, Any]:
    body = {
        "code": code or f"fx-{uuid.uuid4().hex[:8]}",
        "title": "[FIXTURE] Technical concept",
        "statement": "Technical fixture outcome statement; not academic content.",
        "subject": "biology",
        **extra,
    }
    r = client.post(URL, headers=who.headers, json=body)
    assert r.status_code == 201, r.text
    return dict(r.json())


def test_a_concept_is_mapped_across_editions_and_published_only_after_independent_review(
    client: TestClient, db: Session
) -> None:
    author = Staff(client, db, ["content_author"], BIO_BOTH)
    reviewer = Staff(client, db, ["subject_reviewer"], BIO_BOTH)
    c = _concept(client, author)
    assert c["status"] == "draft"
    xi, xii = _topics(db, 11)[0], _topics(db, 12)[0]
    mapped = client.put(f"{URL}/{c['id']}/topics", headers=author.headers, json={"topic_ids": [xi, xii]})
    assert mapped.status_code == 200, mapped.text
    assert {t["grade"] for t in mapped.json()["topics"]} == {11, 12}  # one concept, both books: never duplicated

    no_sources = client.post(f"{URL}/{c['id']}/publish", headers=reviewer.headers)
    assert no_sources.status_code == 422  # a published outcome cites its source
    chapter, doc = _chapter(db, 11, "biology")
    assert chapter.pdf_start is not None
    refs = {
        "source_refs": [{"source_document_id": str(doc.id), "pdf_from": chapter.pdf_start, "pdf_to": chapter.pdf_start}]
    }
    assert client.put(f"{URL}/{c['id']}", headers=author.headers, json=refs).status_code == 200
    assert client.post(f"{URL}/{c['id']}/publish", headers=author.headers).status_code == 403  # not by its author
    published = client.post(f"{URL}/{c['id']}/publish", headers=reviewer.headers)
    assert published.status_code == 200 and published.json()["status"] == "published"
    assert client.put(f"{URL}/{c['id']}", headers=author.headers, json={"title": "Changed"}).status_code == 409
    listed = client.get(URL, headers=author.headers, params={"subject": "biology", "grade": 12}).json()
    assert any(x["id"] == c["id"] for x in listed)


def test_prerequisites_stay_acyclic_and_may_name_a_bridging_lesson(client: TestClient, db: Session) -> None:
    author = Staff(client, db, ["content_author"], BIO_BOTH)
    a, b, c = (_concept(client, author) for _ in range(3))

    def require(x: dict[str, Any], y: dict[str, Any], **extra: Any) -> Any:
        return client.post(
            f"{URL}/{x['id']}/prerequisites", headers=author.headers, json={"requires_id": y["id"], **extra}
        )

    assert require(a, b).status_code == 200
    assert require(b, c).status_code == 200
    cycle = require(c, a)
    assert cycle.status_code == 422 and cycle.json()["code_reason"] == "PREREQUISITE_CYCLE"
    assert require(a, a).status_code == 422
    assert require(a, b).status_code == 200  # adding the same edge again changes nothing
    missing_lesson = require(c, _concept(client, author), bridging_lesson_id=str(uuid.uuid4()))
    assert missing_lesson.status_code == 422
    graph = client.get(f"{URL}/{a['id']}", headers=author.headers).json()
    assert [p["requires_id"] for p in graph["prerequisites"]] == [b["id"]]
    assert client.delete(f"{URL}/{a['id']}/prerequisites/{b['id']}", headers=author.headers).status_code == 200
    assert require(c, a).status_code == 200  # no longer a cycle


def test_scope_and_subject_rules(client: TestClient, db: Session) -> None:
    xii_only = Staff(client, db, ["content_author"], {"grades": [12], "subjects": ["biology"]})
    c = _concept(client, xii_only)
    xi_topic = _topics(db, 11)[0]
    assert (
        client.put(f"{URL}/{c['id']}/topics", headers=xii_only.headers, json={"topic_ids": [xi_topic]}).status_code
        == 403
    )
    chem = _topics(db, 12, "chemistry")[0]
    other_subject = client.put(f"{URL}/{c['id']}/topics", headers=xii_only.headers, json={"topic_ids": [chem]})
    assert other_subject.status_code == 422  # a Biology concept maps to Biology topics
    physics_author = Staff(client, db, ["content_author"], {"grades": [11, 12], "subjects": ["physics"]})
    assert client.put(f"{URL}/{c['id']}", headers=physics_author.headers, json={"title": "x"}).status_code == 404
    learner = Staff(client, db, [])
    assert client.get(URL, headers=learner.headers).status_code == 403
    bad_code = client.post(
        URL,
        headers=xii_only.headers,
        json={"code": "Not A Code!", "title": "x", "statement": "x", "subject": "biology"},
    )
    assert bad_code.status_code == 422
    dup = client.post(
        URL, headers=xii_only.headers, json={"code": c["code"], "title": "x", "statement": "x", "subject": "biology"}
    )
    assert dup.status_code == 409
