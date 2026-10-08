"""Teacher marking (W06.S1, §20.10): scoped queue without learner identity, leases, expected-version decisions,
rubric-bound awards, immutable score versions and learner-visible results only after release. Fixture content only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _learner, _map, _png, _seal, _start, _upload


def _reviewer(client: TestClient, grade: int = 12, subject: str = "chemistry") -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, ["subject_reviewer"], {"grades": [grade], "subjects": [subject]})


def _sealed_script(client: TestClient, chapter: str) -> tuple[Staff, dict[str, Any]]:
    learner = _learner(client)
    a = _start(client, learner, chapter)
    page = _upload(client, learner, a["id"], _png(seed=int(uuid.uuid4().int % 250))).json()["pages"][0]["id"]
    m = _map(client, learner, a, {"1:a": {"pages": [page]}, "1:b": {"unanswered": True}}).json()
    assert _seal(client, learner, a["id"], m["manifest_revision"]).status_code == 200
    return learner, a


def _case_for(client: TestClient, who: Staff, attempt_id: str) -> dict[str, Any]:
    queue = client.get("/v1/studio/written/queue", headers=who.headers).json()
    return next(c for c in queue if c["reference"] == attempt_id[:8])


def _decide(
    client: TestClient, who: Staff, case_id: str, version: int, awards: dict[str, Any], release: bool = False
) -> Any:
    return client.post(
        f"/v1/studio/written/cases/{case_id}/decision",
        headers=who.headers,
        json={"expected_version": version, "awards": awards, "release": release, "reason": "Fixture marking"},
    )


GOOD = {"1": {"a1": {"units": 100, "reason": "Half the expected points"}, "b1": {"units": 0}, "b2": {"units": 0}}}


def test_queue_is_scoped_and_hides_learner_identity(client: TestClient, published_written: dict[str, Any]) -> None:
    learner, a = _sealed_script(client, published_written["chapter"])
    reviewer, outsider = _reviewer(client), _reviewer(client, 11, "physics")
    case = _case_for(client, reviewer, a["id"])
    assert case["status"] == "queued" and case["case_kind"] == "initial"
    assert learner.email not in str(case)
    assert all(
        c["reference"] != a["id"][:8] for c in client.get("/v1/studio/written/queue", headers=outsider.headers).json()
    )
    assert client.get(f"/v1/studio/written/cases/{case['id']}", headers=outsider.headers).status_code == 404
    assert client.get("/v1/studio/written/queue", headers=learner.headers).status_code == 403
    detail = client.get(f"/v1/studio/written/cases/{case['id']}", headers=reviewer.headers).json()
    assert detail["questions"][0]["rubric"]["criteria"] and len(detail["pages"]) == 1
    page = client.get(
        f"/v1/studio/written/cases/{case['id']}/pages/{detail['pages'][0]['id']}", headers=reviewer.headers
    )
    assert page.status_code == 200 and page.headers["cache-control"] == "private, no-store"


def test_leases_and_expected_versions_prevent_silent_overwrites(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    _, a = _sealed_script(client, published_written["chapter"])
    first, second = _reviewer(client), _reviewer(client)
    case = _case_for(client, first, a["id"])
    assert _decide(client, first, case["id"], 0, GOOD).status_code == 409  # no lease yet
    assert client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=first.headers).status_code == 200
    taken = client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=second.headers)
    assert taken.status_code == 409 and "Another teacher" in taken.json()["detail"]
    saved = _decide(client, first, case["id"], 0, GOOD)
    assert saved.status_code == 200 and saved.json()["version"] == 1 and saved.json()["latest"]["total_units"] == 100
    stale = _decide(client, first, case["id"], 0, GOOD)
    assert stale.status_code == 409 and stale.json()["current_version"] == 1


def test_awards_must_follow_the_rubric(client: TestClient, published_written: dict[str, Any]) -> None:
    _, a = _sealed_script(client, published_written["chapter"])
    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, a["id"])
    client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)
    cases = [
        ({"1": {"a1": {"units": 75}, "b1": {"units": 0}, "b2": {"units": 0}}}, "isn't a permitted award"),
        ({"1": {"a1": {"units": 100}, "b1": {"units": 150}, "b2": {"units": 0}}}, "declared this part unanswered"),
        ({"1": {"a1": {"units": 100}, "b1": {"units": 0}}}, "give an award for criterion b2"),
        ({"1": {"a1": {"units": 100}, "b1": {"units": 0}, "b2": {"units": 0}, "zz": {"units": 0}}}, "unknown criteria"),
    ]
    for awards, message in cases:
        r = _decide(client, reviewer, case["id"], 0, awards)
        assert r.status_code == 422 and any(message in e for e in r.json()["errors"]), (message, r.json())


def test_results_are_visible_only_after_release(client: TestClient, published_written: dict[str, Any]) -> None:
    learner, a = _sealed_script(client, published_written["chapter"])
    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, a["id"])
    client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)
    assert _decide(client, reviewer, case["id"], 0, GOOD).status_code == 200
    pending = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
    assert pending["status"] == "pending" and pending["questions"] == []  # a saved draft mark is not a result
    released = _decide(client, reviewer, case["id"], 1, GOOD, release=True)
    assert released.status_code == 200 and released.json()["status"] == "released"
    result = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
    assert result["status"] == "released" and result["total_units"] == 100 and result["max_units"] == 500
    assert result["decision_method"] == "TEACHER" and result["version"] == 2
    a1 = next(c for c in result["questions"][0]["criteria"] if c["id"] == "a1")
    assert a1["earned_units"] == 100 and a1["reason"] == "Half the expected points"
    assert all(
        c["reference"] != a["id"][:8] for c in client.get("/v1/studio/written/queue", headers=reviewer.headers).json()
    )
    other = _learner(client)
    assert client.get(f"/v1/written-attempts/{a['id']}/result", headers=other.headers).status_code == 404


def test_alternative_routes_and_dependencies_are_credited_once() -> None:
    from portal_api.modules.written.review import _check_awards
    from tests.test_written_records import _rubric

    rubric = _rubric(str(uuid.uuid4()))
    rubric["criteria"].append(
        {
            "id": "a2",
            "subpart_id": "a",
            "description": "Depends on a1",
            "max_units": 0,
            "levels": [0],
            "depends_on": ["a1"],
        }
    )
    ctx = {
        "manifest": {"slots": {"1:a": {"pages": ["p"]}, "1:b": {"pages": ["p"]}}},
        "questions": [{"position": 1, "rubric": rubric}],
    }
    both = {"1": {"a1": {"units": 200}, "a2": {"units": 0}, "b1": {"units": 300}, "b2": {"units": 300}}}
    _, errors = _check_awards(ctx, both)
    assert any("only one route" in e for e in errors)
    one = {"1": {"a1": {"units": 200}, "a2": {"units": 0}, "b1": {"units": 150}, "b2": {"units": 0}}}
    totals, errors = _check_awards(ctx, one)
    assert errors == [] and totals == {"1": 350}
