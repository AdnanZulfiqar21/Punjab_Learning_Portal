"""W07.S1.T3 (MODEL-ANSWER-01): versioned release of written worked answers.

A rubric may carry a reviewed worked answer. A learner sees it only in a released result, for a question that was
marked, from the marking-guide version that marked it; never in the attempt or before marks are released, and never
for a question still pending. When an academic correction marked the answer under a corrected guide, or a correction is
still waiting to be applied, the result says so.

Real PostgreSQL; technical fixture questions, rubrics and worked answers in their own chapter.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from tests.test_rubric_adjudication import AW, Team

WORKED = [{"type": "paragraph", "text": "Fixture worked answer: technical text, not academic content."}]


def _plain(blocks: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    """Blocks as authored (the stored copy also records each block's schema version)."""
    return None if blocks is None else [{k: v for k, v in b.items() if k != "v"} for b in blocks]


def _result(client: TestClient, who: Any, attempt_id: str) -> dict[str, Any]:
    return dict(client.get(f"/v1/written-attempts/{attempt_id}/result", headers=who.headers).json())


def test_worked_answers_come_only_with_released_marks_from_the_guide_that_marked(client: TestClient) -> None:
    team = Team(client, 2, "biology")
    early, first = team.sealed(seed=1701)  # pinned to the guide without a worked answer

    team.correct_rubric(lambda b: b.update(model_answer=WORKED))
    learner, a = team.sealed(seed=1702)  # pinned to the guide with the worked answer
    seen = client.get(f"/v1/written-attempts/{a['id']}", headers=learner.headers)
    assert seen.status_code == 200 and "Fixture worked answer" not in seen.text  # never in the attempt
    assert "Fixture worked answer" not in json.dumps(_result(client, learner, a["id"]))  # nor before release

    pending = {"1": {"status": "pending", "reason": "Fixture: page too blurred to read"}}
    assert team.decide(a["id"], "initial", awards={}, question_status=pending).status_code == 200
    q = _result(client, learner, a["id"])["questions"][0]
    assert q["status"] == "pending" and q["model_answer"] is None  # no mark yet, so no worked answer

    assert team.decide(a["id"], "completion", awards=AW).status_code == 200
    q = _result(client, learner, a["id"])["questions"][0]
    assert _plain(q["model_answer"]) == WORKED and q["model_answer_note"] is None

    # The earlier script, marked under its own pinned guide, gets no worked answer.
    assert team.decide(first["id"], "initial", awards=AW).status_code == 200
    q = _result(client, early, first["id"])["questions"][0]
    assert q["status"] == "scored" and q["model_answer"] is None


def test_a_corrected_guide_says_so_with_its_worked_answer(client: TestClient) -> None:
    team = Team(client, 3, "biology")
    learner, a = team.sealed(seed=1703)  # pinned to version 1
    team.correct_rubric(lambda b: b.update(model_answer=WORKED))
    adj = team.adjudicate()  # version 1 -> 2 is an approved correction
    assert adj.status_code == 201, adj.text
    assert team.run(adj.json()["id"])["status"] == "succeeded"
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    q = _result(client, learner, a["id"])["questions"][0]
    assert _plain(q["model_answer"]) == WORKED
    assert (
        q["model_answer_note"] == "This worked answer is from the corrected marking guide your answer was marked under."
    )


def test_a_stored_rubric_with_fields_from_a_newer_build_stays_readable() -> None:
    """Rollback safety: a build reads saved rubrics leniently (fields it doesn't know are ignored), while authoring
    stays strict, so a field added later never stops an older build from marking."""
    from portal_api.modules.content import written as wq

    body = {
        "criteria": [{"id": "a1", "description": "Fixture", "max_units": 100, "levels": [0, 100], "future_hint": "x"}],
        "future_field": {"anything": True},
    }
    strict, errors = wq.parse_rubric(body)
    assert strict is None and errors
    lenient, errors = wq.parse_rubric(body, stored=True)
    assert lenient is not None and not errors and lenient.criteria[0].id == "a1"
