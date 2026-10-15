"""W09.S1.T1 (LIFECYCLE-01): operators see each stage of the written script lifecycle with the count behind every
time, and outcomes are counted apart (accepted, pending, delayed, released). Technical fixtures only; the shared test
database holds other scripts, so the checks compare counts before and after this test's own scripts."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_question_outcomes import _awards, _decide, _sealed, _staff
from tests.test_written_attempts import _learner, _start

URL = "/v1/ops/written-lifecycle?grade=12&subject=chemistry"


def _report(client: TestClient, who: Staff) -> dict[str, Any]:
    r = client.get(URL, headers=who.headers)
    assert r.status_code == 200, r.text
    return dict(r.json())


def test_only_operators_with_mfa_read_the_lifecycle(client: TestClient) -> None:
    with get_sessionmaker()() as db:
        learner = Staff(client, db, [])
        no_mfa = Staff(client, db, ["platform_operator"])
    assert client.get(URL, headers=learner.headers).status_code == 403
    assert client.get(URL, headers=no_mfa.headers).status_code == 403


def test_each_stage_counts_its_own_scripts_and_outcomes_stay_apart(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    operator = _staff(client, ["platform_operator"], mfa=True)
    before = _report(client, operator)

    _, released = _sealed(client, published_written["chapter"], seed=521)
    assert (
        _decide(
            client, _staff(client, ["subject_reviewer"]), released["id"], "initial", {"awards": _awards(q1=100, q2=100)}
        ).status_code
        == 200
    )
    _, waiting = _sealed(client, published_written["chapter"], seed=522)
    with get_sessionmaker()() as db:  # the service obligation passes while it waits
        db.execute(
            text("update written_review_case set due_at = now() - interval '1 hour' where attempt_id = :a"),
            {"a": waiting["id"]},
        )
        db.commit()
    _start(client, _learner(client), published_written["chapter"], question_count=2)  # still writing

    after = _report(client, operator)
    delta = {k: after["outcomes"][k] - before["outcomes"][k] for k in after["outcomes"]}
    assert delta == {
        "started": 3,
        "accepted": 2,
        "not_submitted": 0,
        "not_submitted_plan_withdrawn": 0,
        "still_writing": 1,
        "pending": 1,
        "delayed": 1,
        "released_by_teacher": 1,
        "released_automatically": 0,
    }
    counts = {s["stage"]: s["count"] for s in after["stages"]}
    was = {s["stage"]: s["count"] for s in before["stages"]}
    assert counts["seal"] - was["seal"] == 2
    assert counts["publication"] - was["publication"] == 1  # only the released script has a publication time
    assert counts["review"] - was["review"] == 1 and counts["queue"] - was["queue"] == 1
    uploads = ("upload_while_writing", "upload_after_writing")
    assert sum(counts[k] - was[k] for k in uploads) == 2  # one page each, counted per page
    for s in after["stages"]:
        assert s["count"] == 0 or (s["median_minutes"] is not None and s["median_minutes"] >= 0)
    assert any("B10" in n for n in after["not_running"])
    assert after["days"] == 30 and after["grade"] == 12 and after["subject"] == "chemistry"
