"""P06.S3.T3 release rollback (ROLLBACK-01) and P06.S4.T2 portable export (EXPORT-01). Lesson text is a technical
fixture used only to exercise the workflow."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.modules.audit.models import AuditEvent
from tests import test_content_workflow
from tests.test_content_workflow import FIXTURE_BODY, Staff, _confirm_rights, _post, _refs, _save, _submitted

team = test_content_workflow.team  # the Class XI Biology staff fixture


def _publish_two_versions(client: TestClient, db: Session, team: dict[str, Staff]) -> tuple[dict[str, Any], Any]:
    item, chapter, doc = _submitted(client, db, team)
    _confirm_rights(client, db, doc)
    approve = {"decision": "approve", "comment": "Checked against source pages"}
    assert _post(client, team["reviewer"], item["id"], "review", approve).status_code == 200
    assert _post(client, team["publisher"], item["id"], "publish").status_code == 200
    rev = _post(client, team["author"], item["id"], "revise", {"reason": "Fixture second version"}).json()
    changed = {"blocks": [*FIXTURE_BODY["blocks"], {"type": "paragraph", "text": "Fixture added paragraph."}]}
    assert _save(client, team["author"], rev, body=changed, refs=_refs(chapter, doc)).status_code == 200
    assert _post(client, team["author"], item["id"], "submit").status_code == 200
    assert _post(client, team["reviewer"], item["id"], "review", approve).status_code == 200
    v2 = _post(client, team["publisher"], item["id"], "publish")
    assert v2.status_code == 200 and v2.json()["published_version"] == 2
    return item, chapter


def test_rollback_restores_the_previous_version_without_erasing_history(
    client: TestClient, db: Session, team: dict[str, Staff]
) -> None:
    item, chapter = _publish_two_versions(client, db, team)
    detail = client.get(f"/v1/studio/items/{item['id']}", headers=team["publisher"].headers).json()
    assert detail["actions"]["rollback"] is True
    assert _post(client, team["author"], item["id"], "rollback", {"reason": "Fixture: author can't"}).status_code == 403
    q = _post(client, team["publisher"], item["id"], "quarantine", {"reason": "Fixture: v2 looks wrong"})
    assert q.status_code == 200
    back = _post(client, team["publisher"], item["id"], "rollback", {"reason": "Fixture: v2 broke the page"})
    assert back.status_code == 200, back.text
    assert back.json()["published_version"] == 1 and back.json()["availability"] == "live"
    live = next(x for x in client.get(f"/v1/chapters/{chapter.id}/lessons").json() if x["id"] == item["id"])
    assert live["version"] == 1
    again = _post(client, team["publisher"], item["id"], "rollback", {"reason": "Fixture: nothing earlier"})
    assert again.status_code == 409
    history = client.get(f"/v1/studio/items/{item['id']}/history", headers=team["publisher"].headers).json()
    rolled = [h for h in history if h["action"] == "content.rolled_back"]
    assert len(rolled) == 1 and rolled[0]["details"]["from_version"] == 2 and rolled[0]["details"]["to_version"] == 1
    # Version 2 is kept as history, never deleted; a new revision continues from there.
    versions = {v["number"]: v["status"] for v in _export_items(client, team, chapter)[item["id"]]["versions"]}
    assert versions == {1: "published", 2: "superseded"}


def _export_items(client: TestClient, team: dict[str, Staff], chapter: Any) -> dict[str, Any]:
    r = client.get("/v1/studio/export?grade=11&subject=biology", headers=team["publisher"].headers)
    assert r.status_code == 200, r.text
    doc = json.loads(r.content)
    return {i["id"]: i for i in doc["items"]}


def test_export_is_scoped_audited_and_portable(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    item, chapter = _publish_two_versions(client, db, team)
    r = client.get("/v1/studio/export?grade=11&subject=biology", headers=team["publisher"].headers)
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment;")
    assert r.headers["cache-control"] == "private, no-store"
    doc = json.loads(r.content)
    assert doc["format"] == "portal-content-export" and doc["schema_version"] == 1
    assert doc["grade"] == 11 and doc["subject"] == "biology"
    assert any(c["key"] == chapter.natural_key for c in doc["chapters"])
    mine = next(i for i in doc["items"] if i["id"] == item["id"])
    assert mine["chapter"] == chapter.natural_key and mine["published_version"] == 2
    assert [v["number"] for v in mine["versions"]] == [1, 2] and mine["versions"][0]["source_refs"]
    raw = r.text
    for private in ("password", "@example.com"):
        assert private not in raw  # no learner data or staff identities
    # Out of scope, author-only and non-MFA staff are refused.
    assert (
        client.get("/v1/studio/export?grade=12&subject=biology", headers=team["publisher"].headers).status_code == 403
    )
    assert client.get("/v1/studio/export?grade=11&subject=biology", headers=team["author"].headers).status_code == 403
    no_mfa = Staff(client, db, ["publisher"], {"grades": [11], "subjects": ["biology"]})
    assert client.get("/v1/studio/export?grade=11&subject=biology", headers=no_mfa.headers).status_code == 403
    audited = db.scalars(
        select(AuditEvent).where(
            AuditEvent.action == "content.exported", AuditEvent.actor_user_id == team["publisher"].id
        )
    ).all()
    assert audited and audited[-1].details["items"] >= 1 and audited[-1].details["bytes"] == len(r.content)
