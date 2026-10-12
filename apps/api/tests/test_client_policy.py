"""P13.S1.T4 (CLIENTS-01): supported app versions and build capability manifests. Raising a platform's minimum gives
learners 14 days' notice and never takes effect inside a scheduled mock window; once in effect, a native app below it
is told to update (426) everywhere except the policy check, configuration, sign-out and health; an app that doesn't
state its version is not judged. A build's manifest is registered once and never changes. Fixture accounts only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.modules.system import clients
from tests.test_content_workflow import Staff
from tests.test_mocks import _publish_profile


def _operator(client: TestClient, db: Session) -> Staff:
    return Staff(client, db, ["platform_operator"], None, mfa=True)


def _minimum(client: TestClient, who: Staff, platform: str, version: str, **extra: Any) -> Any:
    body = {"min_version": version, "reason": "Fixture: version policy test", **extra}
    return client.put(f"/v1/ops/clients/{platform}/minimum", headers=who.headers, json=body)


def _policy(client: TestClient, platform: str, version: str) -> dict[str, Any]:
    r = client.get("/v1/clients/policy", params={"platform": platform, "version": version})
    assert r.status_code == 200, r.text
    return dict(r.json())


def _when(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def test_raising_the_minimum_gives_notice_and_spares_mock_windows(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    op = _operator(client, db)
    assert _minimum(client, Staff(client, db, []), "android", "2.0.0").status_code == 403
    soon = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    short = _minimum(client, op, "android", "2.0.0", enforce_at=soon)
    assert short.status_code == 409 and short.json()["code_reason"] == "NOTICE_TOO_SHORT"
    assert _minimum(client, op, "android", "2.0").status_code == 422  # three numbers

    made = _minimum(client, op, "android", "2.0.0")
    assert made.status_code == 200, made.text
    android = next(p for p in made.json() if p["platform"] == "android")
    assert timedelta(days=13, hours=23) < _when(android["enforce_at"]) - datetime.now(UTC) <= timedelta(days=14)
    old = _policy(client, "android", "1.9.3")
    assert old["status"] == "update_soon" and old["min_version"] == "2.0.0" and old["enforce_at"]
    assert (
        _policy(client, "android", "2.0.0")["status"] == "ok" and _policy(client, "android", "10.0.0")["status"] == "ok"
    )

    # A scheduled mock window: the minimum can't take effect inside it, and one scheduled over it pushes it back.
    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 3}])
    version_id = db.execute(
        text(
            "select v.id from exam_profile_version v join exam_profile p on p.id = v.profile_id "
            "where p.code = :c and v.status = 'published'"
        ),
        {"c": code},
    ).scalar_one()
    start = datetime.now(UTC) + timedelta(days=20)
    db.execute(
        text(
            "insert into mock_session (id, profile_version_id, title, timezone, starts_at, entry_closes_at, "
            "window_closes_at, results_at, late_entry, status, created_by) values (:id, :v, 'Fixture window', "
            "'Asia/Karachi', :s, :e, :c, :r, 'fixed_end', 'scheduled', :u)"
        ),
        {
            "id": str(uuid.uuid4()),
            "v": str(version_id),
            "s": start,
            "e": start + timedelta(hours=1),
            "c": start + timedelta(hours=3),
            "r": start + timedelta(days=1),
            "u": str(op.id),
        },
    )
    db.commit()
    inside = _minimum(client, op, "ios", "2.0.0", enforce_at=(start + timedelta(hours=2)).isoformat())
    assert inside.status_code == 409 and inside.json()["code_reason"] == "IN_MOCK_WINDOW"
    before = _minimum(client, op, "ios", "2.0.0", enforce_at=(start - timedelta(days=1)).isoformat())
    assert before.status_code == 200
    db.execute(  # a window later scheduled over that moment
        text("update mock_session set starts_at = :s where title = 'Fixture window' and starts_at = :old"),
        {"s": start - timedelta(days=2), "old": start},
    )
    db.commit()
    ios = next(p for p in client.get("/v1/ops/clients", headers=op.headers).json() if p["platform"] == "ios")
    assert _when(ios["enforce_at"]) == start + timedelta(hours=3)  # deferred to the window's close

    lowered = _minimum(client, op, "android", "1.0.0")  # a rollback applies at once
    assert lowered.status_code == 200 and _policy(client, "android", "1.9.3")["status"] == "ok"
    _minimum(client, op, "ios", "1.0.0")


def test_an_app_below_the_enforced_minimum_is_told_to_update(client: TestClient, db: Session) -> None:
    op = _operator(client, db)
    learner = Staff(client, db, [])
    assert _minimum(client, op, "ios", "3.0.0").status_code == 200
    db.execute(  # time passes: the notice period is over
        text(
            "update client_version_policy set enforce_at = now() - interval '1 minute' "
            "where platform = 'ios' and min_version = '3.0.0'"
        )
    )
    db.commit()
    clients._cache.clear()
    try:

        def me(version: str | None, platform: str = "ios") -> Any:
            headers = {**learner.headers, "X-Portal-Platform": platform}
            if version:
                headers["X-Portal-App-Version"] = version
            return client.get("/v1/me", headers=headers)

        old = me("2.9.9")
        assert old.status_code == 426, old.text
        assert old.json()["code_reason"] == "UPDATE_REQUIRED" and old.json()["min_version"] == "3.0.0"
        assert old.headers["x-content-type-options"] == "nosniff"  # still a hardened response
        assert me("3.0.0").status_code == 200 and me("3.1.0").status_code == 200
        assert me(None).status_code == 200  # an app that doesn't say its version isn't judged
        assert me("2.9.9", platform="android").status_code == 200  # another platform's policy
        stuck = client.get(
            "/v1/clients/policy",
            params={"platform": "ios", "version": "2.9.9"},
            headers={"X-Portal-Platform": "ios", "X-Portal-App-Version": "2.9.9"},
        )
        assert stuck.status_code == 200 and stuck.json()["status"] == "update_required"  # it can still find out why
    finally:
        _minimum(client, op, "ios", "1.0.0")
        clients._cache.clear()


def test_a_build_manifest_is_registered_once(client: TestClient, db: Session) -> None:
    op = _operator(client, db)
    version = f"9.{uuid.uuid4().int % 1000}.0"
    body = {
        "platform": "android",
        "app_version": version,
        "renderer_version": 1,
        "pack_format_version": 1,
        "block_types": {"paragraph": 1, "equation": 1, "diagram": 1},
        "equation_renderer": None,
        "font_set": "Fixture fonts",
    }
    assert client.post("/v1/ops/clients/manifests", headers=Staff(client, db, []).headers, json=body).status_code == 403
    assert client.post("/v1/ops/clients/manifests", headers=op.headers, json=body).status_code == 201
    assert client.post("/v1/ops/clients/manifests", headers=op.headers, json=body).status_code == 201  # same build
    changed = client.post("/v1/ops/clients/manifests", headers=op.headers, json={**body, "renderer_version": 2})
    assert changed.status_code == 409  # a build never changes
    android = next(p for p in client.get("/v1/ops/clients", headers=op.headers).json() if p["platform"] == "android")
    assert any(m["app_version"] == version and m["font_set"] == "Fixture fonts" for m in android["manifests"])
