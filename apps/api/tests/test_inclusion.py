"""P05.S2 (INCLUSION-01): inclusion records say whether a published concept is included, excluded, not applicable or
unverified in an independent mapping (full curriculum, board syllabus, MDCAT, ECAT; per year), with a reason, the source
and its version. Publication needs the source version and an independent academic reviewer. Reports list concepts no
mapping covers yet and contradictions between mappings; coverage counts the published content behind included
concepts. Technical fixture concepts and records only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_concepts import BIO_BOTH, _concept, _topics
from tests.test_concepts import URL as CONCEPTS
from tests.test_content_workflow import Staff, _chapter

URL = "/v1/studio/inclusion"
MDCAT_2026 = {"subject": "biology", "scope": "mdcat", "year": 2026}


def _published_concept(client: TestClient, db: Session, author: Staff, reviewer: Staff) -> dict[str, Any]:
    c = _concept(client, author)
    assert (
        client.put(
            f"{CONCEPTS}/{c['id']}/topics", headers=author.headers, json={"topic_ids": _topics(db, 11)[:1]}
        ).status_code
        == 200
    )
    chapter, doc = _chapter(db, 11, "biology")
    refs = [{"source_document_id": str(doc.id), "pdf_from": chapter.pdf_start, "pdf_to": chapter.pdf_start}]
    assert client.put(f"{CONCEPTS}/{c['id']}", headers=author.headers, json={"source_refs": refs}).status_code == 200
    assert client.post(f"{CONCEPTS}/{c['id']}/publish", headers=reviewer.headers).status_code == 200
    return c


def _record(client: TestClient, who: Staff, concept: dict[str, Any], **extra: Any) -> Any:
    body = {
        "concept_id": concept["id"],
        "scope": "mdcat",
        "year": 2026,
        "state": "included",
        "reason": "Listed in the fixture syllabus section 3.",
        "source": "Technical fixture syllabus document",
        "source_version": "fixture-v1",
        **extra,
    }
    return client.post(URL, headers=who.headers, json=body)


def test_records_are_reviewed_before_publication_and_scopes_stay_independent(client: TestClient, db: Session) -> None:
    author = Staff(client, db, ["content_author"], BIO_BOTH)
    reviewer = Staff(client, db, ["subject_reviewer"], BIO_BOTH)
    c = _published_concept(client, db, author, reviewer)
    draft = _concept(client, author)
    assert _record(client, author, draft).status_code == 422  # only published concepts are mapped

    mdcat = _record(client, author, c)
    assert mdcat.status_code == 201, mdcat.text
    assert mdcat.json()["status"] == "draft"
    full = _record(client, author, c, scope="full_curriculum", year=None, state="included")
    assert full.status_code == 201, full.text
    assert _record(client, author, c).status_code == 409  # one record per concept, mapping and year
    no_version = _record(client, author, c, scope="ecat", source_version="")
    assert no_version.status_code == 422  # a mapping names the version of its source

    rid = mdcat.json()["id"]
    assert client.post(f"{URL}/{rid}/publish", headers=author.headers).status_code == 403  # not its author
    published = client.post(f"{URL}/{rid}/publish", headers=reviewer.headers)
    assert published.status_code == 200 and published.json()["status"] == "published"
    assert client.put(f"{URL}/{rid}", headers=author.headers, json={"state": "excluded"}).status_code == 409  # frozen

    listed = client.get(URL, headers=author.headers, params={"scope": "mdcat", "year": 2026}).json()
    assert any(r["id"] == rid for r in listed) and not any(r["scope"] != "mdcat" for r in listed)


def test_reports_show_gaps_and_contradictions(client: TestClient, db: Session) -> None:
    author = Staff(client, db, ["content_author"], BIO_BOTH)
    reviewer = Staff(client, db, ["subject_reviewer"], BIO_BOTH)
    mapped, unmapped = (_published_concept(client, db, author, reviewer) for _ in range(2))
    a = _record(client, author, mapped, scope="full_curriculum", year=None, state="excluded").json()
    b = _record(client, author, mapped, scope="mdcat", state="included").json()
    for r in (a, b):
        assert client.post(f"{URL}/{r['id']}/publish", headers=reviewer.headers).status_code == 200

    report = client.get(f"{URL}/report", headers=author.headers, params=MDCAT_2026).json()
    assert unmapped["id"] in [x["concept_id"] for x in report["unmapped"]]
    assert mapped["id"] not in [x["concept_id"] for x in report["unmapped"]]
    clash = [x for x in report["contradictions"] if x["concept_id"] == mapped["id"]]
    assert clash and "excluded" in clash[0]["detail"] and "included" in clash[0]["detail"]

    coverage = client.get(f"{URL}/coverage", headers=author.headers, params=MDCAT_2026).json()
    row = next(x for x in coverage["concepts"] if x["concept_id"] == mapped["id"])
    assert row["included"] is True and {"live_lessons", "live_questions", "approved_lectures"} <= set(row)
    assert coverage["included"] >= 1 and 0 <= coverage["with_lessons"] <= coverage["included"]


def test_inclusion_scope_rules(client: TestClient, db: Session) -> None:
    author = Staff(client, db, ["content_author"], BIO_BOTH)
    reviewer = Staff(client, db, ["subject_reviewer"], BIO_BOTH)
    c = _published_concept(client, db, author, reviewer)
    physics = Staff(client, db, ["content_author"], {"grades": [11, 12], "subjects": ["physics"]})
    assert _record(client, physics, c).status_code == 404  # outside the author's subjects
    assert _record(client, author, c, scope="astrology").status_code == 422
    assert _record(client, author, c, state="maybe").status_code == 422
    assert _record(client, author, c, scope="mdcat", year=None).status_code == 422  # exam mappings name a year
    learner = Staff(client, db, [])
    assert client.get(URL, headers=learner.headers).status_code == 403
    assert client.get(
        f"{URL}/report", headers=author.headers, params={"subject": "biology", "scope": "mdcat"}
    ).status_code in (200, 422)
    unknown = client.post(f"{URL}/{uuid.uuid4()}/publish", headers=reviewer.headers)
    assert unknown.status_code == 404


def test_the_learners_syllabus_meter_reads_verified_records(client: TestClient, db: Session) -> None:
    from tests.test_attempts import _learner

    author = Staff(client, db, ["content_author"], BIO_BOTH)
    reviewer = Staff(client, db, ["subject_reviewer"], BIO_BOTH)
    learner = _learner(client)
    profile = {"grade": 11, "subjects": ["biology"], "target_exams": ["mdcat"], "target_year": 2031}

    def meter() -> dict[str, Any]:
        body = client.get("/v1/me/dashboard", headers=learner.headers).json()
        return next(m for m in body["meters"] if m["key"] == "syllabus_coverage")

    assert client.put("/v1/me/profile", headers=learner.headers, json=profile).status_code == 200
    assert meter()["percent"] is None  # no verified MDCAT 2031 records yet: never a syllabus from book headings
    c = _published_concept(client, db, author, reviewer)
    rec = _record(client, author, c, scope="mdcat", year=2031, state="included").json()
    assert meter()["percent"] is None  # a draft record is not verified
    assert client.post(f"{URL}/{rec['id']}/publish", headers=reviewer.headers).status_code == 200
    m = meter()
    assert m["denominator"] >= 1 and m["numerator"] <= m["denominator"] and m["percent"] is not None
    no_year = {**profile, "target_year": None}
    assert client.put("/v1/me/profile", headers=learner.headers, json=no_year).status_code == 200
    assert meter()["percent"] is None  # an exam mapping needs the learner's exam year
