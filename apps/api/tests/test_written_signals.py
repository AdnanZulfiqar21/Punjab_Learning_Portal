"""W07.S2.T3 (WRITTEN-SIGNALS-01): written learning signals stay apart from the binary MCQ evidence model.

Written practice records its own typed events: started, submitted and each released result. A result keeps marks as
units out of a maximum (partial credit is never turned into right or wrong) and counts pending and unavailable
questions apart, adding no units for them. None of it feeds `evidence_rules_v2` or the MCQ progress figures, and
there is no public percentile, rank or leaderboard anywhere. Scripts and marks are technical fixtures.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.main import create_app
from portal_api.modules.analytics import events
from portal_api.modules.analytics.events import AnalyticsEvent
from tests.test_written_marking import _case_for, _decide, _reviewer, _sealed_script


def _written_events(user_id: Any) -> dict[str, list[dict[str, Any]]]:
    with get_sessionmaker()() as db:
        rows = db.scalars(
            select(AnalyticsEvent).where(AnalyticsEvent.user_id == user_id, AnalyticsEvent.name.like("written.%"))
        ).all()
        out: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            out.setdefault(r.name, []).append(dict(r.properties))
        return out


def test_written_practice_records_typed_events_with_units_not_right_or_wrong(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, attempt = _sealed_script(client, published_written["chapter"])
    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, attempt["id"])
    client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)
    partial = {"1": {"a1": {"units": 100, "reason": "Fixture: half"}, "b1": {"units": 0}, "b2": {"units": 0}}}
    assert _decide(client, reviewer, case["id"], 0, partial, release=True).status_code == 200

    got = _written_events(learner.id)
    assert [e["attempt_id"] for e in got["written.started"]] == [attempt["id"]]
    assert got["written.submitted"] == [
        {"attempt_id": attempt["id"], "pages": 1, "answered_parts": 1, "unanswered_parts": 1}
    ]
    (released,) = got["written.result_released"]
    assert released["earned_units"] == 100 and released["scored_questions"] == 1  # partial credit kept as units
    assert released["pending_questions"] == 0 and released["case_kind"] == "initial"
    assert not set(released) & {"correct", "accuracy", "score", "percentile", "rank"}

    # Written work is not MCQ evidence: no topic is demonstrated or even counted from it, and MCQ progress is unchanged.
    evidence = client.get("/v1/me/evidence", headers=learner.headers, params={"grade": 12, "subject": "chemistry"})
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["rules_version"] == "evidence_rules_v2"
    assert all(o["total_weight"] == 0 and o["state"] == "insufficient_evidence" for o in evidence.json()["outcomes"])
    progress = client.get("/v1/me/progress", headers=learner.headers).json()
    assert all(s["questions_answered"] == 0 and s["tests"] == 0 for s in progress["subjects"])


def test_a_pending_question_adds_no_units(client: TestClient, published_written: dict[str, Any]) -> None:
    learner, attempt = _sealed_script(client, published_written["chapter"])
    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, attempt["id"])
    client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)
    body = {
        "expected_version": 0,
        "awards": {},
        "release": True,
        "reason": "Fixture marking",
        "question_status": {"1": {"status": "pending", "reason": "Fixture: too faint to read."}},
    }
    r = client.post(f"/v1/studio/written/cases/{case['id']}/decision", headers=reviewer.headers, json=body)
    assert r.status_code == 200, r.text
    (released,) = _written_events(learner.id)["written.result_released"]
    assert released["pending_questions"] == 1 and released["scored_questions"] == 0
    assert released["earned_units"] == 0 and released["scored_max_units"] == 0  # pending is never a zero mark
    assert released["completeness"] != "complete"


def test_no_percentile_rank_or_leaderboard_is_offered() -> None:
    spec = create_app().openapi()
    words = re.compile(r"percentile|leaderboard|ranking|\brank\b", re.I)
    assert not [p for p in spec["paths"] if words.search(p)]
    for name, schema in spec["components"]["schemas"].items():
        assert not words.search(name), name
        assert not [f for f in schema.get("properties", {}) if words.search(f)], name
    for name in ("written.started", "written.submitted", "written.result_released"):
        assert events.DICTIONARY[name].emitted
        assert not set(events.DICTIONARY[name].props) & {"correct", "accuracy"}
