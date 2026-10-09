"""P05.S3 (EXAMPROFILE-01): versioned exam profiles with two-person verification. The profile values here are
technical fixtures, not official exam patterns."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_content_workflow import Staff

RULES: dict[str, Any] = {
    "source_url": "https://example.invalid/fixture-notice",
    "source_note": "Fixture: technical profile for tests, not an official pattern.",
    "duration_minutes": 60,
    "marks_per_question": 1,
    "negative_marks": 0,
    "sections": [
        {"subject": "biology", "grades": [11, 12], "questions": 10},
        {"subject": "chemistry", "grades": [11, 12], "questions": 5},
    ],
}


def test_two_people_must_verify_before_publication(client: TestClient, db: Session) -> None:
    author = Staff(client, db, ["academic_adjudicator"], mfa=True)
    first, second = Staff(client, db, ["academic_adjudicator"], mfa=True), Staff(client, db, ["owner_admin"], mfa=True)
    learner = Staff(client, db, [])
    code = f"FIXTURE-{uuid.uuid4().hex[:6].upper()}"
    assert (
        client.post("/v1/admin/exam-profiles", headers=learner.headers, json={"code": code, "name": "x"}).status_code
        == 403
    )
    no_mfa = Staff(client, db, ["academic_adjudicator"])
    assert client.get("/v1/admin/exam-profiles", headers=no_mfa.headers).status_code == 403
    made = client.post(
        "/v1/admin/exam-profiles",
        headers=author.headers,
        json={"code": code, "name": "Fixture profile", "eligibility_note": "Fixture: no admission claim."},
    )
    assert made.status_code == 201, made.text
    pid = next(p["id"] for p in made.json() if p["code"] == code)
    bad = {**RULES, "sections": [{"subject": "astrology", "grades": [11], "questions": 3}]}
    assert (
        client.post(
            f"/v1/admin/exam-profiles/{pid}/versions", headers=author.headers, json={"year": 2026, "rules": bad}
        ).status_code
        == 422
    )
    v = client.post(
        f"/v1/admin/exam-profiles/{pid}/versions", headers=author.headers, json={"year": 2026, "rules": RULES}
    )
    assert v.status_code == 201, v.text
    vid = v.json()["id"]
    assert v.json()["total_questions"] == 15 and v.json()["status"] == "draft"
    url = f"/v1/admin/exam-profile-versions/{vid}"
    note = {"note": "Fixture: compared counts and duration with the notice."}
    assert client.post(f"{url}/verify", headers=author.headers, json=note).status_code == 403  # not the author
    assert client.post(f"{url}/publish", headers=author.headers).status_code == 409  # unverified
    assert client.post(f"{url}/verify", headers=first.headers, json=note).json()["verifications"] == 1
    assert client.post(f"{url}/verify", headers=first.headers, json=note).status_code == 409  # a second person
    done = client.post(f"{url}/verify", headers=second.headers, json=note)
    assert done.json()["status"] == "verified" and done.json()["verifications"] == 2
    edit = client.put(
        f"/v1/admin/exam-profiles/{pid}/versions/{vid}", headers=author.headers, json={"year": 2026, "rules": RULES}
    )
    assert edit.status_code == 409  # only drafts change
    assert client.post(f"{url}/publish", headers=second.headers).json()["status"] == "published"
    listed = client.get("/v1/exam-profiles", headers=learner.headers).json()
    mine = next(p for p in listed if p["code"] == code)
    assert mine["version"] == 1 and mine["total_questions"] == 15 and mine["duration_minutes"] == 60

    # A newer version retires the old one for new mocks; only one is published at a time.
    v2 = client.post(
        f"/v1/admin/exam-profiles/{pid}/versions",
        headers=author.headers,
        json={"year": 2027, "rules": {**RULES, "duration_minutes": 90}},
    ).json()
    for who in (first, second):
        client.post(f"/v1/admin/exam-profile-versions/{v2['id']}/verify", headers=who.headers, json=note)
    assert client.post(f"/v1/admin/exam-profile-versions/{v2['id']}/publish", headers=first.headers).status_code == 200
    statuses = {
        x["version"]: x["status"]
        for x in next(
            p for p in client.get("/v1/admin/exam-profiles", headers=author.headers).json() if p["id"] == pid
        )["versions"]
    }
    assert statuses == {1: "retired", 2: "published"}
    assert (
        next(p for p in client.get("/v1/exam-profiles", headers=learner.headers).json() if p["code"] == code)["year"]
        == 2027
    )
