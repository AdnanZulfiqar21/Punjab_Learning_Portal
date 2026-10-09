"""P16.S1.T2 (ACADEMIC-OVERVIEW-01): per-chapter coverage, pipeline, quarantines and pool sufficiency.

Publishes its own fixture question in a Class XI Mathematics chapter so other modules' exact pool counts are not
disturbed."""

from __future__ import annotations

import copy
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs
from tests.test_mcq_items import CHECKS, VALID, _new_mcq, _save

SCOPE = {"grades": [11], "subjects": ["mathematics"]}
Q = {"grade": 11, "subject": "mathematics"}


def _row(client: TestClient, who: Staff, chapter_id: str) -> dict[str, Any]:
    r = client.get("/v1/studio/overview", headers=who.headers, params=Q)
    assert r.status_code == 200, r.text
    return dict(next(c for c in r.json()["chapters"] if c["chapter_id"] == chapter_id))


def test_overview_counts_the_pipeline_live_families_and_quarantines(client: TestClient, db: Session) -> None:
    author, reviewer = Staff(client, db, ["content_author"], SCOPE), Staff(client, db, ["subject_reviewer"], SCOPE)
    publisher = Staff(client, db, ["publisher"], SCOPE, mfa=True)
    chapter, doc = _chapter(db, 11, "mathematics", 3)
    cid = str(chapter.id)
    before = _row(client, publisher, cid)
    item = _new_mcq(client, author, cid)
    body = copy.deepcopy(VALID)
    assert _save(client, author, item, body, _refs(chapter, doc)).status_code == 200
    assert _row(client, publisher, cid)["drafts"] == before["drafts"] + 1
    assert _post(client, author, item["id"], "submit").status_code == 200
    assert _row(client, publisher, cid)["in_review"] == before["in_review"] + 1
    review = {"decision": "approve", "comment": "Fixture check", "checklist": CHECKS}
    assert _post(client, reviewer, item["id"], "review", review).status_code == 200
    _confirm_rights(client, db, doc)
    assert _post(client, publisher, item["id"], "publish").status_code == 200
    live = _row(client, publisher, cid)
    assert live["live_mcq_families"] == before["live_mcq_families"] + 1
    assert live["pool_sufficient"] == (live["live_mcq_families"] >= 3)
    assert _post(client, publisher, item["id"], "quarantine", {"reason": "Fixture", "level": "SOFT"}).status_code == 200
    q = _row(client, publisher, cid)
    assert q["live_mcq_families"] == before["live_mcq_families"] and q["quarantined"] == before["quarantined"] + 1
    _post(client, publisher, item["id"], "retire", {"reason": "Fixture overview done"})
    learner = Staff(client, db, [])
    other = Staff(client, db, ["publisher"], {"grades": [12], "subjects": ["mathematics"]}, mfa=True)
    assert client.get("/v1/studio/overview", headers=learner.headers, params=Q).status_code == 403
    assert client.get("/v1/studio/overview", headers=other.headers, params=Q).status_code == 403
