"""W07.S1.T2 (FEEDBACK-EVIDENCE-01): a teacher's feedback can point to the place on the script it is about.

Each criterion's award may name pages of that question's sealed answer, each with an optional region of the upright
page preview. Anchors that aren't grounded (another question's page, another script's page, a region outside the page)
are refused. The learner's released result names each place in plain words ("page 1, top left") and says so plainly
when a scan is no longer available, never showing an invented highlight. Scripts and marks are technical fixtures.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.written import storage
from portal_api.modules.written.models import WrittenPage
from tests.test_written_marking import _case_for, _decide, _reviewer, _sealed_script


def _first_page(client: TestClient, learner: Any, attempt_id: str) -> str:
    pages = client.get(f"/v1/written-attempts/{attempt_id}", headers=learner.headers).json()["pages"]
    return str(pages[0]["id"])


def _awards(evidence: list[dict[str, Any]] | None) -> dict[str, Any]:
    a1: dict[str, Any] = {"units": 100, "reason": "Fixture: the first step is shown here"}
    if evidence is not None:
        a1["evidence"] = evidence
    return {"1": {"a1": a1, "b1": {"units": 0}, "b2": {"units": 0}}}


def test_feedback_points_to_grounded_places(client: TestClient, published_written: dict[str, Any]) -> None:
    learner, a = _sealed_script(client, published_written["chapter"])
    other_learner, other = _sealed_script(client, published_written["chapter"])
    page, foreign = _first_page(client, learner, a["id"]), _first_page(client, other_learner, other["id"])
    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, a["id"])
    client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)

    for bad in (
        [{"page_id": foreign}],  # another learner's script
        [{"page_id": page, "region": [0.8, 0.0, 0.4, 0.2]}],  # runs off the page
        [{"page_id": page, "region": [0.1, 0.1, 0.0, 0.2]}],  # no area
        [{"page_id": page, "region": ["a", 0, 1, 1]}],
        [{"page_id": page}] * 7,  # too many places for one criterion
    ):
        refused = _decide(client, reviewer, case["id"], 0, _awards(bad))
        assert refused.status_code == 422, (bad, refused.text)

    places = [{"page_id": page, "region": [0.0, 0.0, 0.3333, 0.3333]}, {"page_id": page}]
    released = _decide(client, reviewer, case["id"], 0, _awards(places), release=True)
    assert released.status_code == 200, released.text
    result = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
    a1 = next(c for c in result["questions"][0]["criteria"] if c["id"] == "a1")
    assert [(e["page_number"], e["where"], e["available"]) for e in a1["evidence"]] == [
        (1, "page 1, top left", True),
        (1, "page 1", True),
    ]
    assert a1["evidence"][0]["region"] == [0.0, 0.0, 0.3333, 0.3333] and a1["evidence"][1]["region"] is None
    b1 = next(c for c in result["questions"][0]["criteria"] if c["id"] == "b1")
    assert b1["evidence"] == []  # feedback without a place is shown without one

    # Once the scan is gone, the place is still named but nothing is highlighted.
    with get_sessionmaker()() as db:
        key = db.scalar(select(WrittenPage.preview_key).where(WrittenPage.id == page))
    assert key
    path = storage.get_store().root / key
    data = path.read_bytes()
    path.unlink()
    try:
        gone = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
        a1 = next(c for c in gone["questions"][0]["criteria"] if c["id"] == "a1")
        assert [(e["where"], e["available"], e["region"]) for e in a1["evidence"]] == [
            ("page 1, top left", False, None),
            ("page 1", False, None),
        ]
    finally:
        path.write_bytes(data)
