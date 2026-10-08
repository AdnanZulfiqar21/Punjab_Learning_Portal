"""Premium and preview lessons (review R07; ACCESS-02). Lesson bodies are technical fixtures, not academic content."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.modules.audit.models import AuditEvent
from tests.test_content_workflow import Staff, _confirm_rights, _post, _submitted


@pytest.fixture
def crew(client: TestClient, db: Session) -> dict[str, Staff]:
    bio11 = {"grades": [11], "subjects": ["biology"]}
    return {
        "author": Staff(client, db, ["content_author"], bio11),
        "reviewer": Staff(client, db, ["subject_reviewer"], bio11),
        "publisher": Staff(client, db, ["publisher"], bio11, mfa=True),
        "publisher_no_mfa": Staff(client, db, ["publisher"], bio11),
        "outsider": Staff(client, db, ["publisher"], {"grades": [12], "subjects": ["physics"]}, mfa=True),
    }


def _published(client: TestClient, db: Session, crew: dict[str, Staff]) -> tuple[dict[str, Any], str]:
    item, chapter, doc = _submitted(client, db, crew)
    _confirm_rights(client, db, doc)
    assert (
        _post(
            client, crew["reviewer"], item["id"], "review", {"decision": "approve", "comment": "Checked fixture"}
        ).status_code
        == 200
    )
    assert _post(client, crew["publisher"], item["id"], "publish").status_code == 200
    return item, str(chapter.id)


def _mine(client: TestClient, chapter_id: str, item_id: str, headers: dict[str, str] | None = None) -> tuple[Any, Any]:
    r = client.get(f"/v1/chapters/{chapter_id}/lessons", headers=headers or {})
    assert r.status_code == 200, r.text
    return next(x for x in r.json() if x["id"] == item_id), r.headers


def test_premium_lessons_need_an_active_plan_and_are_never_publicly_cached(
    client: TestClient, db: Session, crew: dict[str, Staff]
) -> None:
    item, chapter = _published(client, db, crew)

    anon, h = _mine(client, chapter, item["id"])
    assert anon["locked"] and anon["body"] is None and anon["block_types"] == [] and anon["title"]
    assert h["cache-control"].startswith("public") and "Authorization" in h["vary"]  # holds no premium body

    no_plan = Staff(client, db, [])
    locked, h = _mine(client, chapter, item["id"], no_plan.headers)
    assert locked["locked"] and locked["body"] is None and h["cache-control"] == "private, no-store"

    learner = Staff(client, db, [])
    assert client.post("/v1/me/trial", headers=learner.headers).status_code == 200
    full, h = _mine(client, chapter, item["id"], learner.headers)
    assert not full["locked"] and full["body"]["blocks"] and h["cache-control"] == "private, no-store"


def test_a_publisher_marks_free_previews_with_a_reason(client: TestClient, db: Session, crew: dict[str, Staff]) -> None:
    item, chapter = _published(client, db, crew)
    body = {"tier": "preview", "reason": "Fixture: chapter opener"}
    assert _post(client, crew["author"], item["id"], "access-tier", body).status_code == 403
    assert _post(client, crew["publisher_no_mfa"], item["id"], "access-tier", body).status_code == 403
    assert _post(client, crew["outsider"], item["id"], "access-tier", body).status_code == 403  # out of scope
    short = _post(client, crew["publisher"], item["id"], "access-tier", {"tier": "preview", "reason": "x"})
    assert short.status_code == 422
    ok = _post(client, crew["publisher"], item["id"], "access-tier", body)
    assert ok.status_code == 200 and ok.json()["access_tier"] == "preview"

    anon, _ = _mine(client, chapter, item["id"])
    assert not anon["locked"] and anon["body"]["blocks"]
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.target_id == item["id"], AuditEvent.action.like("%access_tier%"))
    ).all()
    assert len(events) == 1 and events[0].details["reason"] == "Fixture: chapter opener"

    back = _post(client, crew["publisher"], item["id"], "access-tier", {"tier": "premium", "reason": "Fixture: undo"})
    assert back.json()["access_tier"] == "premium"
    assert _mine(client, chapter, item["id"])[0]["locked"]


def test_invalid_credentials_are_refused_not_treated_as_anonymous(
    client: TestClient, db: Session, crew: dict[str, Staff]
) -> None:
    _, chapter = _published(client, db, crew)
    r = client.get(f"/v1/chapters/{chapter}/lessons", headers={"Authorization": "Bearer pls_not-a-session"})
    assert r.status_code == 401
