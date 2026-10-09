"""§6.6 evidence_rules_v2 (EVIDENCE-RULES-01): exhaustive classification, no repeated-family inflation (AC52/AC61)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from portal_api.modules.assessment.evidence import Response, classify

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
OUTCOME = uuid.uuid4()


def _r(family: uuid.UUID, days_ago: float, correct: bool = True, hinted: bool = False) -> Response:
    return Response(
        family_id=family, outcome_id=OUTCOME, at=NOW - timedelta(days=days_ago), correct=correct, hinted=hinted
    )


def test_cold_start_is_insufficient_evidence() -> None:
    assert classify([], NOW) == {}
    one = classify([_r(uuid.uuid4(), 1)], NOW)[OUTCOME]
    assert one.state == "insufficient_evidence" and one.reasons


def test_independent_recent_correct_evidence_demonstrates() -> None:
    fams = [uuid.uuid4() for _ in range(6)]
    c = classify([_r(f, 2) for f in fams], NOW)[OUTCOME]
    assert c.state == "demonstrated" and c.independent_weight == 6 and c.independent_families == 6


def test_repeating_one_family_cannot_demonstrate() -> None:
    fam = uuid.uuid4()
    others = [uuid.uuid4(), uuid.uuid4()]
    rs = [_r(fam, d) for d in (1, 2, 3, 4, 5, 6, 7, 8)] + [_r(f, 2) for f in others]
    c = classify(rs, NOW)[OUTCOME]
    assert c.state != "demonstrated"  # one family is capped at 2 and repeats are exposed (0.25), not independent


def test_old_strong_evidence_needs_recent_confirmation() -> None:
    fams = [uuid.uuid4() for _ in range(8)]
    c = classify([_r(f, 40) for f in fams], NOW)[OUTCOME]
    assert c.state == "developing" and any("Recent confirmation" in r for r in c.reasons)


def test_low_accuracy_is_developing_with_a_reason_and_window_and_age_apply() -> None:
    fams = [uuid.uuid4() for _ in range(8)]
    rs = [_r(f, 3, correct=i < 4) for i, f in enumerate(fams)]
    c = classify(rs, NOW)[OUTCOME]
    assert c.state == "developing" and any("below 80%" in r for r in c.reasons)
    outside = classify([_r(uuid.uuid4(), 91) for _ in range(10)], NOW)
    assert outside == {}  # nothing in the 90-day window
    half = classify([_r(uuid.uuid4(), 60) for _ in range(6)], NOW)[OUTCOME]
    assert half.total_weight == 3 and half.state == "insufficient_evidence"  # aged evidence counts half


def test_hinted_evidence_never_counts_as_independent() -> None:
    fams = [uuid.uuid4() for _ in range(8)]
    c = classify([_r(f, 2, hinted=True) for f in fams], NOW)[OUTCOME]
    assert c.independent_weight == 0 and c.state == "insufficient_evidence"  # 8 x 0.5 = 4 total


def test_every_record_has_exactly_one_state_and_developing_has_reasons() -> None:
    import random

    rng = random.Random(7)  # noqa: S311 - reproducible test data
    fams = [uuid.uuid4() for _ in range(10)]
    for _ in range(300):
        rs = [
            _r(rng.choice(fams), rng.uniform(0, 95), correct=rng.random() < 0.75, hinted=rng.random() < 0.2)
            for _ in range(rng.randint(0, 25))
        ]
        for c in classify(rs, NOW).values():
            assert c.state in ("insufficient_evidence", "developing", "demonstrated")
            if c.state == "developing":
                assert c.reasons


def test_the_evidence_endpoint_reports_every_topic_with_a_state(client: object) -> None:
    from fastapi.testclient import TestClient

    from tests.test_attempts import _learner

    assert isinstance(client, TestClient)
    learner = _learner(client)
    r = client.get("/v1/me/evidence", headers=learner.headers, params={"grade": 11, "subject": "physics"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rules_version"] == "evidence_rules_v2" and body["outcomes"]
    assert {o["state"] for o in body["outcomes"]} == {"insufficient_evidence"}  # cold start: no invented ability
    assert body["meters"]["syllabus_coverage"]["value"] is None
    assert client.get("/v1/me/evidence", params={"grade": 11, "subject": "physics"}).status_code == 401
