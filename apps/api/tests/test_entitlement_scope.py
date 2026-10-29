"""P14.S1.T2 (ENTITLEMENT-SCOPE-01): a granted product opens exactly its scope. A subject package opens practice,
review, written work and premium lessons for its classes and subjects only; an exam package opens mocks for its exam
patterns only; the platform (and the one free trial) opens everything. Written marking units in a package fund only
written work inside that package. A refusal says what the plan doesn't include. Every product here is a labelled
technical fixture granted by finance staff, not a real offer."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from tests.test_access import _start_written
from tests.test_attempts import _form, _learner, _op, _save_ops, _start
from tests.test_content_workflow import Staff
from tests.test_lesson_access import _mine, _published, crew  # noqa: F401 - the crew fixture
from tests.test_mocks import _mock, _publish_profile


def _finance(client: TestClient, db: Session) -> Staff:
    return Staff(client, db, ["finance"], None, mfa=True)


def _product(client: TestClient, finance: Staff, kind: str, scope: dict[str, Any], on_sale: bool = True) -> str:
    code = f"fx-scope-{uuid.uuid4().hex[:8]}"
    body = {
        "code": code,
        "name": "Fixture package",
        "kind": kind,
        "scope": scope,
        "duration_days": 30,
        "written_units": 0,
    }
    made = client.post("/v1/admin/products", headers=finance.headers, json=body)
    assert made.status_code == 201, made.text
    if on_sale:
        on = client.post(
            f"/v1/admin/products/{made.json()['id']}/activate",
            headers=finance.headers,
            json={"reason": "Fixture: on sale"},
        )
        assert on.status_code == 200
    return code


def _grant(client: TestClient, finance: Staff, who: Staff, product: str | None, units: int = 0) -> Any:
    body: dict[str, Any] = {
        "email": who.email,
        "source": "scholarship",
        "days": 30,
        "written_units": units,
        "reason": "Fixture scholarship grant",
    }
    if product is not None:
        body["product_code"] = product
    return client.post("/v1/admin/entitlements", headers=finance.headers, json=body)


def _refused(r: Any, what: str) -> None:
    assert r.status_code == 403, r.text
    assert r.json()["code_reason"] == "NOT_IN_PLAN" and what in r.json()["detail"], r.text


def test_a_subject_package_opens_only_its_classes_and_subjects(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    finance = _finance(client, db)
    phy = _product(client, finance, "subject_package", {"grades": [11], "subjects": ["physics"]})
    bio = _product(client, finance, "subject_package", {"grades": [11], "subjects": ["biology"]})

    a = Staff(client, db, [])
    granted = _grant(client, finance, a, phy)
    assert granted.status_code == 201, granted.text
    assert granted.json()["product_code"] == phy and granted.json()["scope"]["subjects"] == ["physics"]
    assert _form(client, a, physics["chapter"]).status_code == 201

    b = Staff(client, db, [])
    assert _grant(client, finance, b, bio).status_code == 201
    _refused(_form(client, b, physics["chapter"]), "Class 11 Physics")
    mine = client.get("/v1/me/access", headers=b.headers).json()
    assert mine["has_access"] is True  # a plan exists; it just doesn't cover physics
    assert [(e["product_code"], e["scope"]["subjects"]) for e in mine["entitlements"]] == [(bio, ["biology"])]

    draft = _product(client, finance, "subject_package", {"grades": [11], "subjects": ["physics"]}, on_sale=False)
    not_sold = _grant(client, finance, Staff(client, db, []), draft)
    assert not_sold.status_code == 422 and not_sold.json()["code_reason"] == "PRODUCT_NOT_ON_SALE"
    assert _form(client, _learner(client), physics["chapter"]).status_code == 201  # the trial opens everything


def test_premium_lessons_follow_the_package(client: TestClient, db: Session, crew: dict[str, Staff]) -> None:  # noqa: F811
    item, chapter = _published(client, db, crew)  # a premium Class 11 Biology lesson
    finance = _finance(client, db)
    bio = _product(client, finance, "subject_package", {"grades": [11], "subjects": ["biology"]})
    phy12 = _product(client, finance, "subject_package", {"grades": [12], "subjects": ["physics"]})
    reader, other = Staff(client, db, []), Staff(client, db, [])
    _grant(client, finance, reader, bio)
    _grant(client, finance, other, phy12)
    opened, _ = _mine(client, chapter, item["id"], reader.headers)
    assert not opened["locked"] and opened["body"]["blocks"]
    locked, _ = _mine(client, chapter, item["id"], other.headers)
    assert locked["locked"] and locked["body"] is None


def test_an_exam_package_opens_its_mocks_only(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 3}])
    finance = _finance(client, db)
    exam = _product(client, finance, "exam_package", {"exams": [code]})
    phy = _product(client, finance, "subject_package", {"grades": [11], "subjects": ["physics"]})
    candidate, student = Staff(client, db, []), Staff(client, db, [])
    _grant(client, finance, candidate, exam)
    _grant(client, finance, student, phy)

    assert client.get(f"/v1/mocks/{code}/readiness", headers=candidate.headers).json()["entitled"] is True
    assert _mock(client, candidate, code).status_code == 201
    _refused(_form(client, candidate, physics["chapter"]), "Class 11 Physics")  # an exam pass isn't a subject plan

    assert client.get(f"/v1/mocks/{code}/readiness", headers=student.headers).json()["entitled"] is False
    _refused(_mock(client, student, code), code)


def test_package_marking_units_fund_only_that_package(
    client: TestClient, db: Session, published_written: dict[str, Any]
) -> None:
    finance = _finance(client, db)
    chem12 = _product(client, finance, "subject_package", {"grades": [12], "subjects": ["chemistry"]})
    bio11 = _product(client, finance, "subject_package", {"grades": [11], "subjects": ["biology"]})
    chapter = published_written["chapter"]  # Class 12 Chemistry written questions

    funded = Staff(client, db, [])
    _grant(client, finance, funded, chem12, units=10)
    assert _start_written(client, funded, chapter).status_code in (200, 201)

    elsewhere = Staff(client, db, [])
    _grant(client, finance, elsewhere, None, units=0)  # a platform plan with no marking units...
    _grant(client, finance, elsewhere, bio11, units=10)  # ...and biology units, which can't pay for chemistry
    r = _start_written(client, elsewhere, chapter)
    assert r.status_code == 403 and r.json()["title"] == "ALLOWANCE_EXHAUSTED", r.text  # covered, but unfunded


def test_a_started_timed_attempt_outlives_the_plan_but_new_starts_do_not(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    finance = _finance(client, db)
    phy = _product(client, finance, "subject_package", {"grades": [11], "subjects": ["physics"]})
    who = Staff(client, db, [])
    ent = _grant(client, finance, who, phy).json()
    form = _form(client, who, physics["chapter"], timed_minutes=20).json()
    attempt = _start(client, who, form["id"])
    assert attempt["deadline_at"]
    with get_sessionmaker()() as s:  # the plan reaches its normal end mid-attempt
        s.execute(text("update entitlement set ends_at = clock_timestamp() where id = :i"), {"i": ent["id"]})
        s.commit()
    item = attempt["items"][0]
    saved = _save_ops(client, who, attempt["id"], _op(item["position"], 1, item["options"][0]["id"]))
    assert saved.status_code == 200, saved.text  # authorised before the end: it runs to its own deadline
    done = client.post(
        f"/v1/attempts/{attempt['id']}/submit", headers=who.headers, json={"idempotency_key": "scope-outlives-0001"}
    )
    assert done.status_code == 200, done.text
    assert _form(client, who, physics["chapter"]).status_code == 403  # nothing new starts after the plan ends
