"""P06.S1.T2 (ASSIGN-REVIEWER-01): a publisher assigns a reviewer from the people eligible for the item: active
reviewers in its class and subject who didn't edit it. Technical fixture lesson only."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.test_content_workflow import Staff, _post, _submitted


@pytest.fixture
def people(client: TestClient, db: Session) -> dict[str, Staff]:
    bio11 = {"grades": [11], "subjects": ["biology"]}
    return {
        "author": Staff(client, db, ["content_author"], bio11),
        "reviewer": Staff(client, db, ["subject_reviewer"], bio11),
        "lead": Staff(client, db, ["academic_adjudicator"], bio11),  # holds the review permission too
        "away": Staff(client, db, ["subject_reviewer"], bio11),
        "physics": Staff(client, db, ["subject_reviewer"], {"grades": [11], "subjects": ["physics"]}),
        "publisher": Staff(client, db, ["publisher"], bio11, mfa=True),
        "publisher_no_mfa": Staff(client, db, ["publisher"], bio11),
    }


def _options(client: TestClient, who: Staff, item: dict[str, Any]) -> Any:
    return client.get(f"/v1/studio/items/{item['id']}/reviewers", headers=who.headers)


def test_a_publisher_assigns_an_eligible_reviewer_and_can_clear_it(
    client: TestClient, db: Session, people: dict[str, Staff]
) -> None:
    item, _, _ = _submitted(client, db, {"author": people["author"]})
    db.execute(text("update app_user set status = 'suspended' where id = :u"), {"u": str(people["away"].id)})
    db.commit()

    listed = _options(client, people["publisher"], item)
    assert listed.status_code == 200, listed.text
    ids = {o["id"] for o in listed.json()}
    assert {str(people["reviewer"].id), str(people["lead"].id)} <= ids
    assert str(people["away"].id) not in ids  # suspended
    assert str(people["physics"].id) not in ids  # another subject
    assert str(people["author"].id) not in ids  # wrote it (and isn't a reviewer)
    assert _options(client, people["reviewer"], item).status_code == 403  # only publishers list everyone

    detail = client.get(f"/v1/studio/items/{item['id']}", headers=people["publisher"].headers).json()
    assert detail["actions"]["assign"] is True
    assert (
        client.get(f"/v1/studio/items/{item['id']}", headers=people["reviewer"].headers).json()["actions"]["assign"]
        is False
    )

    no_mfa = people["publisher_no_mfa"]
    assert client.get(f"/v1/studio/items/{item['id']}", headers=no_mfa.headers).json()["actions"]["assign"] is False
    refused = _post(client, no_mfa, item["id"], "assign", {"reviewer_id": str(people["reviewer"].id)})
    assert refused.status_code == 403 and "multi-factor" in refused.json()["detail"]

    done = _post(client, people["publisher"], item["id"], "assign", {"reviewer_id": str(people["reviewer"].id)})
    assert done.status_code == 200, done.text
    assert done.json()["assigned_reviewer"] == people["reviewer"].email
    # Only the assigned reviewer may now review; another eligible reviewer may claim it instead.
    lead_view = client.get(f"/v1/studio/items/{item['id']}", headers=people["lead"].headers).json()["actions"]
    assert (lead_view["review"], lead_view["claim"]) == (False, True)

    suspended = _post(client, people["publisher"], item["id"], "assign", {"reviewer_id": str(people["away"].id)})
    assert suspended.status_code == 422 and "isn't active" in suspended.json()["detail"]
    outside = _post(client, people["publisher"], item["id"], "assign", {"reviewer_id": str(people["physics"].id)})
    assert outside.status_code == 422

    cleared = _post(client, people["publisher"], item["id"], "assign", {"reviewer_id": None})
    assert cleared.status_code == 200 and cleared.json()["assigned_reviewer"] is None
    events = (
        db.execute(
            text("select details from audit_event where target_id = :i and action = 'content.reviewer_assigned'"),
            {"i": item["id"]},
        )
        .scalars()
        .all()
    )
    assert [e.get("reviewer_id") for e in events] == [str(people["reviewer"].id), None]
