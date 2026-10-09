"""P06.S1.T1 (CATALOGUE-ADMIN-01): catalogue changes are previewed with their dependencies and applied only as
previewed.

A modified *copy* of the derived catalogue is used (one chapter renamed, one topic dropped, one chapter dropped); the
real catalogue is re-applied afterwards, which reactivates everything, so other tests see the original structure.
The lesson is a technical fixture."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.modules.audit.models import AuditEvent
from portal_api.modules.curriculum.importer import DEFAULT_CATALOGUE
from portal_api.modules.curriculum.models import Chapter, Topic
from tests import test_content_workflow
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _create, _post, _refs, _save

team = test_content_workflow.team


def _write(tmp: Path, catalogue: dict[str, Any]) -> Path:
    path = tmp / "catalogue.json"
    path.write_text(json.dumps(catalogue, ensure_ascii=False), encoding="utf-8")
    return path


def test_preview_shows_changes_and_dependencies_and_apply_is_guarded(
    client: TestClient, db: Session, team: dict[str, Staff], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renamed, _ = _chapter(db, 11, "biology", 5)
    dropped, doc = _chapter(db, 11, "biology", 6)
    topic = db.scalars(select(Topic).where(Topic.chapter_id == renamed.id, Topic.parent_id.is_(None))).first()
    assert topic is not None
    # A published lesson in the chapter that will be retired.
    _confirm_rights(client, db, doc)
    item = _create(client, team["author"], dropped)
    assert _save(client, team["author"], item, refs=_refs(dropped, doc)).status_code == 200
    assert _post(client, team["author"], item["id"], "submit", {"note": "ready"}).status_code == 200
    review = {"decision": "approve", "comment": "Fixture check"}
    assert _post(client, team["reviewer"], item["id"], "review", review).status_code == 200
    assert _post(client, team["publisher"], item["id"], "publish").status_code == 200

    original = json.loads(DEFAULT_CATALOGUE.read_text(encoding="utf-8"))
    changed = copy.deepcopy(original)
    for book in changed["books"]:
        for ch in book["chapters"]:
            if ch["id"] == str(renamed.id):
                ch["title"] = ch["title"] + " (fixture rename)"
                ch["topics"] = [t for t in ch["topics"] if t["id"] != str(topic.id)]
        book["chapters"] = [c for c in book["chapters"] if c["id"] != str(dropped.id)]
    monkeypatch.setenv("PORTAL_CATALOGUE_PATH", str(_write(tmp_path, changed)))

    learner = Staff(client, db, [], mfa=True)
    no_mfa, admin = Staff(client, db, ["owner_admin"]), Staff(client, db, ["owner_admin"], mfa=True)
    for who in (learner, no_mfa):
        assert client.post("/v1/admin/catalogue/preview", headers=who.headers).status_code == 403
    pv = client.post("/v1/admin/catalogue/preview", headers=admin.headers)
    assert pv.status_code == 200, pv.text
    p = pv.json()
    ch = p["changes"]
    assert [c["id"] for c in ch["chapters_retired"]] == [str(dropped.id)]
    assert ch["chapters_renamed"][0]["id"] == str(renamed.id) and ch["chapters_renamed"][0]["to"].endswith("rename)")
    assert str(topic.id) in {t["id"] for t in ch["topics_retired"]}
    assert any(
        d["item_id"] == item["id"] and d["published"] and d["reason"] == "chapter retired" for d in p["dependencies"]
    )
    assert p["published_dependencies"] >= 1

    url = "/v1/admin/catalogue/apply"
    unack = client.post(url, headers=admin.headers, json={"input_sha256": p["input_sha256"]})
    assert unack.status_code == 409 and unack.json()["code_reason"] == "DEPENDENCIES_UNACKNOWLEDGED"
    stale = client.post(url, headers=admin.headers, json={"input_sha256": "0" * 64, "acknowledge_dependencies": True})
    assert stale.status_code == 409 and stale.json()["code_reason"] == "CATALOGUE_CHANGED"
    assert db.get(Chapter, dropped.id).retired_at is None  # type: ignore[union-attr]  # nothing applied yet
    try:
        ok = client.post(
            url, headers=admin.headers, json={"input_sha256": p["input_sha256"], "acknowledge_dependencies": True}
        )
        assert ok.status_code == 200, ok.text
        db.expire_all()
        assert db.get(Chapter, dropped.id).retired_at is not None  # type: ignore[union-attr]
        assert db.get(Chapter, renamed.id).title.endswith("(fixture rename)")  # type: ignore[union-attr]
        assert client.get(f"/v1/chapters/{dropped.id}").status_code == 410  # gone for learners, kept for history
        logged = set(db.scalars(select(AuditEvent.action).where(AuditEvent.actor_user_id == admin.id)))
        assert {"catalogue.previewed", "catalogue.applied"} <= logged
    finally:
        monkeypatch.delenv("PORTAL_CATALOGUE_PATH")
        back = client.post("/v1/admin/catalogue/preview", headers=admin.headers).json()
        assert {c["id"] for c in back["changes"]["chapters_reactivated"]} >= {str(dropped.id)}
        restored = client.post(
            url, headers=admin.headers, json={"input_sha256": back["input_sha256"], "acknowledge_dependencies": True}
        )
        assert restored.status_code == 200, restored.text
    db.expire_all()
    assert db.get(Chapter, dropped.id).retired_at is None  # type: ignore[union-attr]
    assert db.get(Topic, topic.id).retired_at is None  # type: ignore[union-attr]
    assert client.get(f"/v1/chapters/{dropped.id}").status_code == 200
