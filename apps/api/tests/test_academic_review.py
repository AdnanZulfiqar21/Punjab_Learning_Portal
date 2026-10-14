"""W01.S2.T2 / W05.S2.T3 (ACADEMIC-REVIEW-01): methods the marking guide doesn't cover go to academic review.

A teacher keeps such a question pending with an `escalation` instead of forcing a score; releasing opens an academic
review. While it is open the learner sees why, and nobody can mark the question. Only an academic adjudicator in scope
with MFA resolves it: "guide corrected" must name an approved correction of that question's guide, "not covered"
keeps the guide. Resolving never sets a mark; the question is then marked as usual. Everything is audited, and the
learner's export includes their reviews without staff identities.

Real PostgreSQL; technical fixture questions and rubrics in their own chapter (the shared fixture rubric never changes).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from portal_api.db import get_sessionmaker
from portal_api.modules.identity import privacy
from portal_api.modules.identity.models import AppUser
from tests.test_content_workflow import Staff
from tests.test_rubric_adjudication import AW, Team

REVIEWS = "/v1/studio/written/academic-reviews"
UNLISTED = {
    "status": "pending",
    "reason": "Fixture: a valid method the guide doesn't list",
    "escalation": "unlisted_method",
}


def _result(client: TestClient, who: Staff, attempt_id: str) -> dict[str, Any]:
    return dict(client.get(f"/v1/written-attempts/{attempt_id}/result", headers=who.headers).json())


def test_an_unlisted_method_waits_for_academic_review_and_is_never_forced(client: TestClient) -> None:
    team = Team(client, 0, "biology")
    learner, a = team.sealed(seed=1601)
    opened = team.decide(a["id"], "initial", awards={}, question_status={"1": UNLISTED})
    assert opened.status_code == 200, opened.text

    q = _result(client, learner, a["id"])["questions"][0]
    assert (q["status"], q["academic_review"], q["earned_units"]) == ("pending", "open", None)
    assert "doesn't list" in q["status_reason"]

    listed = client.get(REVIEWS, headers=team.adjudicator.headers)
    assert listed.status_code == 200, listed.text
    review = next(r for r in listed.json() if r["reference"] == a["id"][:8])
    assert (review["kind"], review["position"], review["status"]) == ("unlisted_method", 1, "open")
    assert review["rubric_item_id"] == team.rubric_id and review["rubric_version"] == 1
    assert "learner" not in json.dumps(review).lower()  # the learner is never named
    with get_sessionmaker()() as db:
        outsider = Staff(client, db, ["academic_adjudicator"], {"grades": [12], "subjects": ["physics"]}, mfa=True)
    assert all(r["reference"] != a["id"][:8] for r in client.get(REVIEWS, headers=outsider.headers).json())
    assert client.get(REVIEWS, headers=learner.headers).status_code == 403

    # Nobody marks it while the review is open: no score and no "can't be assessed".
    for status in (
        {"awards": AW},
        {"awards": {}, "question_status": {"1": {"status": "unavailable", "reason": "x" * 10}}},
    ):
        blocked = team.decide(a["id"], "completion", **status)
        assert blocked.status_code == 409 and blocked.json()["code_reason"] == "ACADEMIC_REVIEW_OPEN", blocked.text

    url = f"{REVIEWS}/{review['id']}/resolve"
    no_correction = client.post(
        url,
        headers=team.adjudicator.headers,
        json={"resolution": "guide_corrected", "note": "Fixture: the guide was corrected"},
    )
    assert no_correction.status_code == 422 and no_correction.json()["code_reason"] == "CORRECTION_REQUIRED"
    with get_sessionmaker()() as db:
        plain = Staff(client, db, ["academic_adjudicator"], team.scope)  # no MFA
    assert (
        client.post(
            url, headers=plain.headers, json={"resolution": "not_covered", "note": "Fixture note text"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            url, headers=team.marker.headers, json={"resolution": "not_covered", "note": "Fixture note text"}
        ).status_code
        == 403
    )

    # The guide is corrected to cover the method, and the review names that approved correction.
    team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: the alternative method"))
    adj = team.adjudicate()
    assert adj.status_code == 201, adj.text
    done = client.post(
        url,
        headers=team.adjudicator.headers,
        json={
            "resolution": "guide_corrected",
            "note": "Fixture: covered by the corrected guide",
            "adjudication_id": adj.json()["id"],
        },
    )
    assert done.status_code == 200, done.text
    assert (done.json()["status"], done.json()["resolution"]) == ("resolved", "guide_corrected")
    again = client.post(
        url, headers=team.adjudicator.headers, json={"resolution": "not_covered", "note": "Fixture note text"}
    )
    assert again.status_code == 409

    # Now it is marked as usual, and the learner's result and export say what happened.
    assert team.run(adj.json()["id"])["status"] == "succeeded"  # the correction is applied to this script first
    marked = team.decide(a["id"], "completion", awards=AW)
    assert marked.status_code == 200, marked.text
    final = _result(client, learner, a["id"])
    q = final["questions"][0]
    assert (q["status"], q["academic_review"]) == ("scored", "resolved") and q["earned_units"] == 250
    with get_sessionmaker()() as db:
        actions = db.scalars(
            text("select action from audit_event where target_id = :a order by at"), {"a": a["id"]}
        ).all()
        assert {"written.academic_review_opened", "written.academic_review_resolved"} <= set(actions)
        user = db.scalar(select(AppUser).where(AppUser.id == learner.id))
        assert user is not None
        exported = json.loads(privacy.export(db, user)[0])
    rows = exported["written"]["academic_reviews"]
    assert [(r["position"], r["resolution"]) for r in rows] == [(1, "guide_corrected")]
    assert not any(k.endswith("_by") for k in rows[0])  # staff identities stay out


def test_an_escalation_is_only_for_a_pending_question_and_never_with_a_learner_request(client: TestClient) -> None:
    team = Team(client, 1, "biology")
    _, a = team.sealed(seed=1602)
    bad = [
        {**UNLISTED, "status": "scored"},
        {**UNLISTED, "learner_action": "rescan"},
        {**UNLISTED, "escalation": "guess"},
    ]
    for status in bad:
        r = team.decide(a["id"], "initial", awards={}, question_status={"1": status})
        assert r.status_code == 422, (status, r.text)
    # "Not covered" keeps the guide: then the question is marked under it as usual.
    assert (
        team.decide(
            a["id"], "initial", awards={}, question_status={"1": {**UNLISTED, "escalation": "rubric_defect"}}
        ).status_code
        == 200
    )
    review = next(
        r for r in client.get(REVIEWS, headers=team.adjudicator.headers).json() if r["reference"] == a["id"][:8]
    )
    assert review["kind"] == "rubric_defect"
    wrong = client.post(
        f"{REVIEWS}/{review['id']}/resolve",
        headers=team.adjudicator.headers,
        json={"resolution": "not_covered", "note": "Fixture: the guide stands", "adjudication_id": str(uuid.uuid4())},
    )
    assert wrong.status_code == 422  # only a corrected guide names a correction
    kept = client.post(
        f"{REVIEWS}/{review['id']}/resolve",
        headers=team.adjudicator.headers,
        json={"resolution": "not_covered", "note": "Fixture: the guide stands"},
    )
    assert kept.status_code == 200 and kept.json()["resolution"] == "not_covered"
    assert team.decide(a["id"], "completion", awards=AW).status_code == 200
