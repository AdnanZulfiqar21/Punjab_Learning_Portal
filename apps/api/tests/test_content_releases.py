"""P06.S3.T2 (CONTENT-RELEASE-01): several approved items published together, or none of them, and rolled back together.

Lesson text is a technical fixture used only to exercise the workflow."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests import test_content_workflow
from tests.test_content_workflow import (
    FIXTURE_BODY,
    Staff,
    _chapter,
    _confirm_rights,
    _create,
    _post,
    _refs,
    _save,
    _submitted,
)

team = test_content_workflow.team  # the Class XI Biology staff fixture

APPROVE = {"decision": "approve", "comment": "Checked against source pages"}


def _approved(client: TestClient, db: Session, team: dict[str, Staff]) -> tuple[dict[str, Any], Any, Any]:
    item, chapter, doc = _submitted(client, db, team)
    _confirm_rights(client, db, doc)
    assert _post(client, team["reviewer"], item["id"], "review", APPROVE).status_code == 200
    return item, chapter, doc


def _approved_in(client: TestClient, db: Session, team: dict[str, Staff], index: int) -> tuple[dict[str, Any], Any]:
    """An approved lesson in another Class XI Biology chapter (by index)."""
    chapter, doc = _chapter(db, 11, "biology", index)
    item = _create(client, team["author"], chapter)
    assert _save(client, team["author"], item, refs=_refs(chapter, doc)).status_code == 200
    assert _post(client, team["author"], item["id"], "submit", {"note": "ready"}).status_code == 200
    _confirm_rights(client, db, doc)
    assert _post(client, team["reviewer"], item["id"], "review", APPROVE).status_code == 200
    return item, chapter


def _release(client: TestClient, who: Staff, ids: list[str], label: str = "Fixture release") -> Any:
    return client.post(
        "/v1/studio/releases",
        headers=who.headers,
        json={"item_ids": ids, "label": label, "reason": "Fixture: publish together"},
    )


def _detail(client: TestClient, who: Staff, item_id: str) -> dict[str, Any]:
    return dict(client.get(f"/v1/studio/items/{item_id}", headers=who.headers).json())


def test_approved_items_are_published_together(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    a, _, _ = _approved(client, db, team)
    b, _, _ = _approved(client, db, team)
    assert _release(client, team["author"], [a["id"], b["id"]]).status_code == 403  # authors don't publish
    assert _release(client, team["publisher_no_mfa"], [a["id"], b["id"]]).status_code == 403  # MFA, as for one item

    r = _release(client, team["publisher"], [a["id"], b["id"], a["id"]])  # a repeated id counts once
    assert r.status_code == 201, r.text
    release = r.json()
    assert release["status"] == "published" and [e["item_id"] for e in release["entries"]] == [a["id"], b["id"]]
    assert all(
        e["version"] == 1 and e["previous_version"] is None and e["availability"] == "live" for e in release["entries"]
    )
    for item in (a, b):
        d = _detail(client, team["publisher"], item["id"])
        assert d["availability"] == "live" and d["published_version"] == 1

    listed = client.get("/v1/studio/releases", headers=team["publisher"].headers).json()
    assert release["id"] in [x["id"] for x in listed]
    outsider = Staff(client, db, ["publisher"], {"grades": [12], "subjects": ["physics"]}, mfa=True)
    assert release["id"] not in [x["id"] for x in client.get("/v1/studio/releases", headers=outsider.headers).json()]
    assert client.get(f"/v1/studio/releases/{release['id']}", headers=outsider.headers).status_code == 404


def test_one_unready_item_publishes_nothing(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    ready, _, _ = _approved(client, db, team)
    submitted, _, _ = _submitted(client, db, team)  # not yet approved
    refused = _release(client, team["publisher"], [ready["id"], submitted["id"]])
    assert refused.status_code == 422
    assert [x["item_id"] for x in refused.json()["items"]] == [submitted["id"]]
    assert _detail(client, team["publisher"], ready["id"])["availability"] == "unpublished"

    # A publication check that fails once both are put live (here its chapter was retired after approval) also
    # leaves both unpublished.
    other, other_chapter = _approved_in(client, db, team, index=1)
    db.execute(text("update chapter set retired_at = now() where id = :id"), {"id": other_chapter.id})
    db.commit()
    try:
        blocked = _release(client, team["publisher"], [ready["id"], other["id"]])
    finally:
        db.execute(text("update chapter set retired_at = null where id = :id"), {"id": other_chapter.id})
        db.commit()
    assert blocked.status_code == 422, blocked.text
    assert [x["item_id"] for x in blocked.json()["items"]] == [other["id"]]
    assert any("retired" in e for e in blocked.json()["items"][0]["errors"])
    for item in (ready, other):
        assert _detail(client, team["publisher"], item["id"])["availability"] == "unpublished"

    # Out-of-scope and edited-by-the-publisher items are refused the same way.
    outsider = Staff(client, db, ["publisher"], {"grades": [12], "subjects": ["physics"]}, mfa=True)
    assert _release(client, outsider, [ready["id"]]).status_code == 422


def test_a_release_is_rolled_back_as_a_whole(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    # Item A is live at version 1 and the release brings version 2; item B is first published by the release.
    a, chapter, doc = _approved(client, db, team)
    assert _post(client, team["publisher"], a["id"], "publish").status_code == 200
    rev = _post(client, team["author"], a["id"], "revise", {"reason": "Fixture second version"}).json()
    changed = {"blocks": [*FIXTURE_BODY["blocks"], {"type": "paragraph", "text": "Fixture added paragraph."}]}
    assert _save(client, team["author"], rev, body=changed, refs=_refs(chapter, doc)).status_code == 200
    assert _post(client, team["author"], a["id"], "submit").status_code == 200
    assert _post(client, team["reviewer"], a["id"], "review", APPROVE).status_code == 200
    b, _, _ = _approved(client, db, team)

    release = _release(client, team["publisher"], [a["id"], b["id"]]).json()
    entries = {e["item_id"]: e for e in release["entries"]}
    assert entries[a["id"]]["version"] == 2 and entries[a["id"]]["previous_version"] == 1

    url = f"/v1/studio/releases/{release['id']}/rollback"
    assert client.post(url, headers=team["author"].headers, json={"reason": "Fixture: author can't"}).status_code == 403
    back = client.post(url, headers=team["publisher"].headers, json={"reason": "Fixture: the release was wrong"})
    assert back.status_code == 200, back.text
    assert back.json()["status"] == "rolled_back"
    da, db_ = _detail(client, team["publisher"], a["id"]), _detail(client, team["publisher"], b["id"])
    assert da["availability"] == "live" and da["published_version"] == 1
    assert db_["availability"] == "unpublished" and db_["state"] == "approved"  # can go out again later
    assert client.post(url, headers=team["publisher"].headers, json={"reason": "Fixture: twice"}).status_code == 409
    history = client.get(f"/v1/studio/items/{b['id']}/history", headers=team["publisher"].headers).json()
    assert any(h["action"] == "content.release_withdrawn" for h in history)

    # B published again on its own; a release whose item has moved on since can't be rolled back.
    again = _release(client, team["publisher"], [b["id"]], label="Fixture again").json()
    assert _post(client, team["author"], b["id"], "revise", {"reason": "Fixture newer"}).status_code == 200
    item_b = _detail(client, team["author"], b["id"])
    assert _save(client, team["author"], item_b, body=changed, refs=_refs(chapter, doc)).status_code == 200
    assert _post(client, team["author"], b["id"], "submit").status_code == 200
    assert _post(client, team["reviewer"], b["id"], "review", APPROVE).status_code == 200
    assert _post(client, team["publisher"], b["id"], "publish").status_code == 200
    moved = client.post(
        f"/v1/studio/releases/{again['id']}/rollback",
        headers=team["publisher"].headers,
        json={"reason": "Fixture: late"},
    )
    assert moved.status_code == 422 and moved.json()["items"][0]["item_id"] == b["id"]
    assert _detail(client, team["publisher"], b["id"])["published_version"] == 2  # unchanged
