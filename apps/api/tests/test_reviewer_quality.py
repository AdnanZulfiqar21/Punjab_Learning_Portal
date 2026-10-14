"""W06.S3.T3 (part; REVIEWER-QUALITY-01): academic leads see each marker's overrides, upheld rechecks and conflicts.

A recheck by another teacher that changes the marks counts against the version it reviewed as "changed"; one that keeps
them counts as "upheld". Only adjudicators see the report, only for their academic scope, and it gives raw counts (no
threshold judges anyone). Technical fixtures only: the marks verify software behaviour, not marking accuracy.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_recheck import _ask, _awards, _mark, _sealed_two_question_script, _staff

URL = "/v1/studio/written/reviewer-quality"


def _row(client: TestClient, who: Staff, marker: Staff) -> dict[str, Any] | None:
    r = client.get(URL, headers=who.headers)
    assert r.status_code == 200, r.text
    return next((x for x in r.json() if x["reviewer_id"] == str(marker.id)), None)


def test_overrides_and_upheld_rechecks_are_counted_per_marker(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed_two_question_script(client, published_written["chapter"], seed=1801)
    first, second, third = (_staff(client, ["subject_reviewer"]) for _ in range(3))
    lead = _staff(client, ["academic_adjudicator"], mfa=True)
    assert _mark(client, first, a["id"], "initial", _awards(q1=100, q2=100)).status_code == 200
    assert _ask(client, learner, a["id"], [1]).status_code == 200
    assert _mark(client, second, a["id"], "recheck", _awards(q1=200)).status_code == 200  # changed
    assert _ask(client, learner, a["id"], [1]).status_code == 200  # an appeal against the correction
    assert _mark(client, third, a["id"], "recheck", _awards(q1=200)).status_code == 200  # upheld

    f = _row(client, lead, first)
    assert f is not None
    assert (f["decisions"], f["rechecked"], f["changed_on_recheck"], f["upheld_on_recheck"]) == (1, 1, 1, 0)
    assert f["scopes"] == ["12:chemistry"] and f["reviewer"].endswith("@example.com")
    s = _row(client, lead, second)
    assert s is not None
    assert (s["decisions"], s["rechecked"], s["changed_on_recheck"], s["upheld_on_recheck"]) == (1, 1, 0, 1)
    t = _row(client, lead, third)
    assert t is not None and (t["decisions"], t["rechecked"]) == (1, 0)

    with get_sessionmaker()() as db:
        elsewhere = Staff(client, db, ["academic_adjudicator"], {"grades": [11], "subjects": ["physics"]}, mfa=True)
    assert _row(client, elsewhere, first) is None  # out of scope
    assert client.get(URL, headers=first.headers).status_code == 403  # markers don't see each other's figures
    assert client.get(URL, headers=learner.headers).status_code == 403
