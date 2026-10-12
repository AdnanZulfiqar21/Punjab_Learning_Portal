"""W06.S1.T3 (CALIBRATION-01): independent calibration of automatic proposals against blinded teacher marking.

On the evaluation subset, the teacher's first released decision (made without ever seeing a proposal) is compared
criterion by criterion with the validated proposal for the same sealed evidence and rubric version. An academic
adjudicator records who applied the rubric correctly for each disagreement; that never changes the teacher's marks or
the learner's result. The proposals come from the deterministic technical fixture assessor; nothing here is a real
assessment.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from portal_api.modules.written import automatic
from portal_api.modules.written.calibration import in_evaluation_subset
from tests.test_content_workflow import Staff
from tests.test_written_automatic import _run
from tests.test_written_marking import _case_for, _decide, _reviewer, _sealed_script

SCOPE = {"grades": [12], "subjects": ["chemistry"]}
URL = "/v1/studio/written/calibration"


def _released(client: TestClient, chapter: str, a1: int) -> tuple[Staff, str]:
    learner, attempt = _sealed_script(client, chapter)
    assert _run(attempt["id"], automatic.FixtureAssessor()) == ["proposed"]  # fixture: full credit on answered parts
    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, attempt["id"])
    client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)
    awards = {"1": {"a1": {"units": a1, "reason": "Fixture marking"}, "b1": {"units": 0}, "b2": {"units": 0}}}
    assert _decide(client, reviewer, case["id"], 0, awards, release=True).status_code == 200
    return learner, attempt["id"]


def _adjudicator(client: TestClient, mfa: bool = True, scope: dict[str, Any] = SCOPE) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, ["academic_adjudicator"], scope, mfa=mfa)


def test_blinded_marks_are_compared_and_adjudicated_without_changing_results(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    chapter = published_written["chapter"]
    learner, differs = _released(client, chapter, a1=100)  # the fixture proposed 200 for a1
    _, agrees = _released(client, chapter, a1=200)

    lead = _adjudicator(client)
    params: dict[str, str | int] = {"grade": 12, "subject": "chemistry"}
    assert client.get(URL, headers=_reviewer(client).headers, params=params).status_code == 403  # teachers stay blind
    assert client.get(URL, headers=_adjudicator(client, mfa=False).headers, params=params).status_code == 403
    outsider = _adjudicator(client, scope={"grades": [11], "subjects": ["biology"]})
    assert client.get(URL, headers=outsider.headers, params=params).status_code == 403

    view = client.get(URL, headers=lead.headers, params=params)
    assert view.status_code == 200 and view.headers["cache-control"] == "private, no-store"
    rows = {c["reference"]: c for c in view.json()["comparisons"]}
    open_row, agreed_row = rows[differs[:8]], rows[agrees[:8]]
    assert open_row["status"] == "open" and open_row["disagreements"] == ["a1"]
    assert (open_row["teacher_units"]["a1"], open_row["proposal_units"]["a1"]) == (100, 200)
    assert agreed_row["status"] == "agreed" and agreed_row["disagreements"] == []
    assert view.json()["compared"] >= 2 and view.json()["agreement_rate"] is not None
    assert "email" not in view.text and "user_id" not in view.text  # no learner identity

    adjudicate = f"{URL}/{open_row['id']}/adjudicate"
    wrong = {"verdicts": {"b1": "teacher"}, "reason": "Fixture: verdict for the wrong criterion"}
    assert client.post(adjudicate, headers=lead.headers, json=wrong).status_code == 422
    verdict = {"verdicts": {"a1": "teacher"}, "reason": "Fixture: the first step is incomplete, so half credit."}
    done = client.post(adjudicate, headers=lead.headers, json=verdict)
    assert (
        done.status_code == 200
        and done.json()["status"] == "adjudicated"
        and done.json()["verdicts"] == {"a1": "teacher"}
    )
    assert client.post(adjudicate, headers=lead.headers, json=verdict).status_code == 409
    agreed_url = f"{URL}/{agreed_row['id']}/adjudicate"
    assert (
        client.post(agreed_url, headers=lead.headers, json={"verdicts": {}, "reason": "Fixture: nothing"}).status_code
        == 409
    )

    # The learner's result is the teacher's, untouched by calibration.
    result = client.get(f"/v1/written-attempts/{differs}/result", headers=learner.headers).json()
    assert result["total_units"] == 100
    # Refreshing again creates nothing new.
    again = client.get(URL, headers=lead.headers, params=params).json()
    assert again["compared"] == view.json()["compared"]


def test_the_evaluation_subset_is_a_fixed_share() -> None:
    ids = [uuid.uuid4() for _ in range(400)]
    assert not any(in_evaluation_subset(i, 0) for i in ids) and all(in_evaluation_subset(i, 100) for i in ids)
    some = [i for i in ids if in_evaluation_subset(i, 25)]
    assert 50 < len(some) < 150  # about a quarter
    assert [in_evaluation_subset(i, 25) for i in ids] == [in_evaluation_subset(i, 25) for i in ids]  # deterministic
