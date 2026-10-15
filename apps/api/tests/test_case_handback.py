"""W06.S1.T2 (CASE-HANDBACK-01, §20.10): a teacher gives a script back to the queue, and an academic adjudicator frees a
script someone else holds, without anything saved being lost or silently overwritten. Technical fixtures only."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_question_outcomes import _awards, _sealed, _staff


def _case_id(client: TestClient, who: Any, attempt_id: str) -> str:
    return next(
        c["id"]
        for c in client.get("/v1/studio/written/queue", headers=who.headers).json()
        if c["reference"] == attempt_id[:8] and c["case_kind"] == "initial"
    )


def _audit(case_id: str, action: str) -> list[dict[str, Any]]:
    with get_sessionmaker()() as db:
        rows = db.execute(
            text("select actor_user_id, details from audit_event where target_id = :t and action = :a"),
            {"t": case_id, "a": action},
        ).all()
    return [{"actor": str(a), "details": d} for a, d in rows]


def test_a_teacher_gives_a_script_back_and_another_can_take_it_at_once(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    _, a = _sealed(client, published_written["chapter"], seed=511)
    first, second = _staff(client, ["subject_reviewer"]), _staff(client, ["subject_reviewer"])
    case = _case_id(client, first, a["id"])
    base = f"/v1/studio/written/cases/{case}"

    assert client.post(f"{base}/lease/release", headers=first.headers).status_code == 409  # nothing to give back
    assert client.post(f"{base}/lease", headers=first.headers).status_code == 200
    assert client.post(f"{base}/lease", headers=second.headers).status_code == 409  # held
    assert client.post(f"{base}/lease/release", headers=second.headers).status_code == 409  # not theirs

    back = client.post(f"{base}/lease/release", headers=first.headers)
    assert back.status_code == 200, back.text
    assert (back.json()["leased_by_me"], back.json()["leased_by_other"], back.json()["lease_expires_at"]) == (
        False,
        False,
        None,
    )
    assert [e["actor"] for e in _audit(case, "written.case_handed_back")] == [str(first.id)]
    taken = client.post(f"{base}/lease", headers=second.headers)
    assert taken.status_code == 200 and taken.json()["leased_by_me"] is True

    # The first teacher can no longer save: their next decision needs the lease.
    late = client.post(
        f"{base}/decision",
        headers=first.headers,
        json={"expected_version": taken.json()["version"], "awards": _awards(q1=100, q2=100), "release": True},
    )
    assert late.status_code == 409


def test_an_adjudicator_frees_a_script_with_a_reason_and_nothing_is_overwritten(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=512)
    away, next_teacher = _staff(client, ["subject_reviewer"]), _staff(client, ["subject_reviewer"])
    lead_no_mfa = _staff(client, ["academic_adjudicator"])
    lead = _staff(client, ["academic_adjudicator"], mfa=True)
    case = _case_id(client, away, a["id"])
    base = f"/v1/studio/written/cases/{case}"

    assert client.post(f"{base}/free", headers=lead.headers, json={"reason": "Fixture"}).status_code == 409  # unheld
    held = client.post(f"{base}/lease", headers=away.headers)
    assert held.status_code == 200
    with get_sessionmaker()() as db:
        started = db.execute(
            text("select marking_started_at from written_review_case where id = :c"), {"c": case}
        ).scalar_one()
    assert started is not None

    detail = client.get(base, headers=lead.headers).json()
    assert (detail["can_free"], detail["leased_by_other"]) == (True, True)
    assert client.get(base, headers=next_teacher.headers).json()["can_free"] is False

    reviewer_try = client.post(f"{base}/free", headers=next_teacher.headers, json={"reason": "Fixture"})
    assert reviewer_try.status_code == 403  # a teacher can't take a colleague's script away
    assert client.post(f"{base}/free", headers=lead_no_mfa.headers, json={"reason": "Fixture"}).status_code == 403
    assert client.post(f"{base}/free", headers=lead.headers, json={"reason": ""}).status_code == 422
    assert client.post(f"{base}/free", headers=lead.headers, json={"reason": "   "}).status_code == 422

    freed = client.post(f"{base}/free", headers=lead.headers, json={"reason": "Fixture: the marker was called away"})
    assert freed.status_code == 200, freed.text
    [event] = _audit(case, "written.case_freed")
    assert event["actor"] == str(lead.id)
    assert event["details"] == {"previous_holder": str(away.id), "reason": "Fixture: the marker was called away"}
    with get_sessionmaker()() as db:
        row = db.execute(
            text("select lease_holder, marking_started_at from written_review_case where id = :c"), {"c": case}
        ).one()
    assert tuple(row) == (None, None)  # the next teacher's marking time starts when they take it

    stale = client.post(
        f"{base}/decision",
        headers=away.headers,
        json={"expected_version": held.json()["version"], "awards": _awards(q1=100, q2=100), "release": True},
    )
    assert stale.status_code == 409  # the teacher who was away can't overwrite anything now
    taken = client.post(f"{base}/lease", headers=next_teacher.headers)
    assert taken.status_code == 200
    done = client.post(
        f"{base}/decision",
        headers=next_teacher.headers,
        json={"expected_version": taken.json()["version"], "awards": _awards(q1=200, q2=100), "release": True},
    )
    assert done.status_code == 200, done.text
    result = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
    assert result["total_units"] == 300 and result["versions"][-1]["version"] == 1  # one release, by the next teacher
    assert client.post(f"{base}/free", headers=lead.headers, json={"reason": "Fixture"}).status_code == 409  # released


def test_an_adjudicator_cannot_free_their_own_lease_or_a_script_out_of_scope(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    _, a = _sealed(client, published_written["chapter"], seed=513)
    lead = _staff(client, ["academic_adjudicator"], mfa=True)
    case = _case_id(client, lead, a["id"])
    base = f"/v1/studio/written/cases/{case}"
    assert client.post(f"{base}/lease", headers=lead.headers).status_code == 200
    own = client.post(f"{base}/free", headers=lead.headers, json={"reason": "Fixture"})
    assert own.status_code == 409 and "give it back" in own.text
    assert client.post(f"{base}/lease/release", headers=lead.headers).status_code == 200

    with get_sessionmaker()() as db:
        from portal_api.modules.identity.permissions import Role
        from tests.test_content_workflow import Staff

        outside = Staff(client, db, [Role.academic_adjudicator.value], {"grades": [11], "subjects": ["biology"]}, True)
    assert client.post(f"{base}/free", headers=outside.headers, json={"reason": "Fixture"}).status_code == 404
