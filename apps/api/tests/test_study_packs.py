"""P13.S3.T1 (OFFLINE-PACKS-01): controlled offline study packs. A pack carries only what the learner may already read
online: preview lessons for anyone, premium lessons and practice under a covering plan; practice questions only from
the practice pool, live, at their published (released) version with its key and explanation; never mock-reserved or
quarantined questions. The manifest's SHA-256 and size match the content exactly, the format is negotiated, and the
pack expires with the covering plan. Technical fixture questions and lessons only."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.modules.content import blocks, packs
from tests.test_attempts import _learner, publish_physics_pool
from tests.test_content_workflow import Staff, _post
from tests.test_lesson_access import _published, crew  # noqa: F401 - the crew fixture


@pytest.fixture(scope="module")
def pack_pool(client: TestClient) -> dict[str, Any]:
    return publish_physics_pool(client, 5)  # its own chapter: these questions are changed below


def _pack(client: TestClient, who: Staff, chapter: str, fmt: int = 1) -> Any:
    return client.get(f"/v1/me/study-packs/{chapter}", params={"format": fmt}, headers=who.headers)


def test_a_pack_holds_only_released_practice_questions_and_checks_out(
    client: TestClient, db: Session, pack_pool: dict[str, Any]
) -> None:
    pub, ids = pack_pool["publisher"], pack_pool["ids"]
    moved = _post(client, pub, ids[0], "question-pool", {"pool": "mock", "reason": "Fixture: mock-only"})
    assert moved.status_code == 200, moved.text
    held = _post(client, pub, ids[1], "quarantine", {"reason": "Fixture: suspected key", "level": "SOFT"})
    assert held.status_code == 200, held.text

    learner = _learner(client)  # the free trial covers everything
    r = _pack(client, learner, pack_pool["chapter"])
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "private, no-store"
    pack = r.json()
    m, raw = pack["manifest"], pack["content"].encode("utf-8")
    assert m["sha256"] == hashlib.sha256(raw).hexdigest() and m["bytes"] == len(raw)
    assert m["pack_format_version"] == packs.PACK_FORMAT_VERSION
    assert m["content_schema_version"] == blocks.CONTENT_SCHEMA_VERSION
    assert m["includes_premium"] is True and m["grade"] == 11 and m["subject"] == "physics"
    trial_end = client.get("/v1/me/access", headers=learner.headers).json()["trial"]["ends_at"]
    assert datetime.fromisoformat(m["expires_at"]) == datetime.fromisoformat(trial_end)

    content = json.loads(pack["content"])
    assert set(content) == {"lessons", "questions", "passages"}  # never a mock or timed form
    packed = {q["id"]: q for q in content["questions"]}
    assert ids[0] not in packed and ids[1] not in packed  # mock-reserved and quarantined stay on the server
    assert set(ids[2:]) <= set(packed)
    for item_id in ids[2:]:
        body = packed[item_id]["body"]
        assert body["correct_option_id"] == pack_pool["keys"][item_id] and body["explanation"]["correct"]
    rows = db.execute(
        text(
            "select i.id::text, i.kind, i.question_pool, i.availability, v.number from content_item i "
            "join content_version v on v.id = i.published_version_id where i.id::text = any(:ids)"
        ),
        {"ids": list(packed)},
    ).all()
    for item_id, kind, pool, availability, number in rows:  # every packed question is released practice, as published
        assert (kind, pool, availability) == ("mcq", "practice", "live")
        assert packed[item_id]["version"] == number
    assert len(rows) == len(packed)


def test_without_a_covering_plan_a_pack_has_previews_only(
    client: TestClient,
    db: Session,
    crew: dict[str, Staff],  # noqa: F811
    pack_pool: dict[str, Any],
) -> None:
    premium, chapter = _published(client, db, crew)  # a premium Class XI Biology lesson
    preview, _ = _published(client, db, crew)
    tier = _post(
        client, crew["publisher"], preview["id"], "access-tier", {"tier": "preview", "reason": "Fixture: free preview"}
    )
    assert tier.status_code == 200, tier.text

    def lesson_ids(who: Staff, at: str) -> tuple[set[str], dict[str, Any]]:
        p = _pack(client, who, at).json()
        return {x["id"] for x in json.loads(p["content"])["lessons"]}, p["manifest"]

    nobody = Staff(client, db, [])
    seen, m = lesson_ids(nobody, chapter)
    assert preview["id"] in seen and premium["id"] not in seen and m["includes_premium"] is False
    expires = datetime.fromisoformat(m["expires_at"]) - datetime.fromisoformat(m["generated_at"])
    assert timedelta(days=packs.PREVIEW_PACK_DAYS - 1) < expires <= timedelta(days=packs.PREVIEW_PACK_DAYS)
    assert m["questions"] == 0
    assert json.loads(_pack(client, nobody, pack_pool["chapter"]).json()["content"])["questions"] == []

    finance = Staff(client, db, ["finance"], None, mfa=True)
    product = client.post(
        "/v1/admin/products",
        headers=finance.headers,
        json={
            "code": f"fx-pack-{premium['id'][:8]}",
            "name": "Fixture physics package",
            "kind": "subject_package",
            "scope": {"grades": [11], "subjects": ["physics"]},
            "duration_days": 30,
            "written_units": 0,
        },
    ).json()
    client.post(f"/v1/admin/products/{product['id']}/activate", headers=finance.headers, json={"reason": "Fixture on"})
    physics_only = Staff(client, db, [])
    grant = {"email": physics_only.email, "source": "scholarship", "days": 30, "written_units": 0}
    client.post(
        "/v1/admin/entitlements",
        headers=finance.headers,
        json={**grant, "reason": "Fixture scholarship grant", "product_code": product["code"]},
    )
    seen, m = lesson_ids(physics_only, chapter)  # a physics plan doesn't open biology
    assert premium["id"] not in seen and m["includes_premium"] is False

    reader = _learner(client)
    seen, m = lesson_ids(reader, chapter)
    assert {premium["id"], preview["id"]} <= seen and m["includes_premium"] is True
    status = client.get(f"/v1/me/study-packs/{chapter}/status", headers=reader.headers).json()
    assert status["keep"] is True and status["includes_premium"] is True


def test_an_app_never_receives_a_pack_newer_than_it_reads(
    client: TestClient, pack_pool: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    learner = _learner(client)
    monkeypatch.setattr(packs, "PACK_FORMAT_VERSION", packs.PACK_FORMAT_VERSION + 1)
    old = _pack(client, learner, pack_pool["chapter"], fmt=packs.PACK_FORMAT_VERSION - 1)
    assert old.status_code == 409 and old.json()["code_reason"] == "PACK_FORMAT_UNSUPPORTED"
    assert "Update the app" in old.json()["detail"]
    assert _pack(client, learner, pack_pool["chapter"], fmt=packs.PACK_FORMAT_VERSION).status_code == 200
