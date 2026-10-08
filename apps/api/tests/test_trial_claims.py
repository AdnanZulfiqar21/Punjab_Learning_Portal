"""Trial claims, device authorization and recovery (review R06; roadmap §16.2-16.7).

Device evidence here comes from the development/test fixture adapter: deterministic verdicts that exercise the
decision table. They are not evidence about any physical device; real DeviceCheck/App Attest and Play Integrity
recall need B07/B08.
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.access import trial_devices
from tests.test_content_workflow import Staff


def _user(client: TestClient, roles: list[str] | None = None, mfa: bool = False) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, roles or [], None, mfa)


def _native(install: str) -> dict[str, str]:
    return {"X-Portal-Client": "native", "X-Portal-Install": install}


def _install() -> str:
    return f"fixture-install-{uuid.uuid4().hex}"


def _claim(
    client: TestClient, who: Staff, install: str, verdict: str = "clean", key: str | None = None, **proof: Any
) -> Any:
    return client.post(
        "/v1/me/trial/claims",
        headers={**who.headers, **_native(install)},
        json={
            "surface": "android",
            "idempotency_key": key or uuid.uuid4().hex,
            "proof": {"fixture_verdict": verdict, **proof},
            "label": "Fixture phone",
        },
    )


def _grants(who: Staff) -> int:
    with get_sessionmaker()() as db:
        return int(
            db.execute(text("select count(*) from trial_grant where user_id = :u"), {"u": str(who.id)}).scalar() or 0
        )


def test_web_activation_is_a_recorded_claim_and_idempotent(client: TestClient) -> None:
    who = _user(client)
    first = client.post("/v1/me/trial", headers=who.headers).json()
    again = client.post("/v1/me/trial", headers=who.headers).json()
    assert first["trial"]["status"] == "active" and again["trial"]["ends_at"] == first["trial"]["ends_at"]
    with get_sessionmaker()() as db:
        row = db.execute(
            text("select status, evidence->>'verdict' from trial_claim where user_id = :u"), {"u": str(who.id)}
        ).one()
    assert row == ("GRANTED", "not_applicable") and _grants(who) == 1


def test_a_clean_native_device_gets_the_trial_and_its_authorization(client: TestClient) -> None:
    who, install = _user(client), _install()
    r = _claim(client, who, install).json()
    assert r["state"] == "granted" and r["claim_status"] == "GRANTED" and r["device_id"]
    devices = client.get("/v1/me/trial/devices", headers={**who.headers, **_native(install)}).json()
    assert len(devices) == 1 and devices[0]["method"] == "first_use" and devices[0]["this_device"]


def test_a_new_account_on_a_consumed_device_gets_no_automatic_trial(client: TestClient) -> None:
    who, install = _user(client), _install()
    key = uuid.uuid4().hex
    r = _claim(client, who, install, verdict="consumed", key=key).json()
    assert r["state"] == "device_used" and r["claim_status"] == "CLOSED_INELIGIBLE"
    assert "already been used on this device" in r["message"]
    assert _claim(client, who, install, verdict="clean", key=key).json()["state"] == "device_used"  # same claim
    assert _grants(who) == 0


def test_a_lost_marker_response_is_recovered_on_the_same_claim(client: TestClient) -> None:
    who, install = _user(client), _install()
    key = uuid.uuid4().hex
    lost = _claim(client, who, install, key=key, fixture_mark="lost").json()
    assert lost["state"] == "verification_pending" and lost["claim_status"] == "MARK_UNKNOWN"
    assert _grants(who) == 0
    recovered = _claim(client, who, install, key=key).json()
    assert recovered["state"] == "granted" and recovered["claim_status"] == "GRANTED"
    retry = _claim(client, who, install, key=key).json()
    assert retry["ends_at"] == recovered["ends_at"] and _grants(who) == 1  # the original dates, never a new period
    with get_sessionmaker()() as db:
        n = db.execute(text("select count(*) from trial_claim where user_id = :u"), {"u": str(who.id)}).scalar()
    assert n == 1  # no replacement claim


def test_unresolved_claims_go_to_review_after_seven_days(client: TestClient) -> None:
    who, install = _user(client), _install()
    key = uuid.uuid4().hex
    assert _claim(client, who, install, key=key, fixture_mark="lost").json()["claim_status"] == "MARK_UNKNOWN"
    with get_sessionmaker()() as db:
        db.execute(
            text("update trial_claim set created_at = created_at - interval '8 days' where user_id = :u"),
            {"u": str(who.id)},
        )
        db.commit()
    r = _claim(client, who, install, key=key).json()
    assert r["state"] == "review_required" and r["claim_status"] == "REVIEW_REQUIRED" and _grants(who) == 0


def test_unknown_evidence_depends_on_the_explicit_mode(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def native_unconfigured(who: Staff, install: str) -> Any:
        return client.post(
            "/v1/me/trial/claims",
            headers={**who.headers, **_native(install)},
            json={"surface": "ios", "idempotency_key": uuid.uuid4().hex, "proof": {}},
        ).json()

    monkeypatch.setattr(trial_devices, "evidence_mode", lambda: "required")
    strict = native_unconfigured(_user(client), _install())
    assert strict["state"] == "verification_pending" and strict["evidence"].startswith("provider_unconfigured")
    monkeypatch.setattr(trial_devices, "evidence_mode", lambda: "fallback")
    who = _user(client)
    lenient = native_unconfigured(who, _install())
    assert lenient["state"] == "granted" and lenient["evidence"].startswith("provider_unconfigured")
    devices = client.get("/v1/me/trial/devices", headers=who.headers).json()
    assert devices[0]["method"] == "fallback"  # recorded: the same-device requirement was not verified


def test_a_web_grant_does_not_unlock_a_consumed_native_device(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    who, install = _user(client), _install()
    assert client.post("/v1/me/trial", headers=who.headers).status_code == 200  # web grant
    r = client.post(
        "/v1/me/trial/devices",
        headers={**who.headers, **_native(install)},
        json={"surface": "android", "proof": {"fixture_verdict": "consumed"}},
    ).json()
    assert r["state"] == "review_required" and _grants(who) == 1  # no new grant, original dates kept
    # Server-side enforcement: protected starts on that native install are refused; the web is unaffected.
    body = {"grade": 12, "subject": "chemistry", "chapter_ids": [published_written["chapter"]], "question_count": 1}
    native = client.post(
        "/v1/written/forms",
        headers={**who.headers, **_native(install), "Idempotency-Key": uuid.uuid4().hex},
        json=body,
    )
    assert native.status_code == 403 and native.json()["title"] == "DEVICE_AUTHORIZATION_REQUIRED"
    web = client.post("/v1/written/forms", headers={**who.headers, "Idempotency-Key": uuid.uuid4().hex}, json=body)
    assert web.status_code == 201


def test_device_limit_removal_and_replacement_window(client: TestClient) -> None:
    who = _user(client)
    first = _install()
    assert _claim(client, who, first).json()["state"] == "granted"
    others = [_install() for _ in range(3)]

    def add(install: str, **extra: Any) -> Any:
        return client.post(
            "/v1/me/trial/devices",
            headers={**who.headers, **_native(install)},
            json={"surface": "android", "proof": {"fixture_verdict": "clean"}, **extra},
        )

    assert add(others[0]).json()["state"] == "device_authorized"
    assert add(others[1]).json()["state"] == "device_authorized"
    assert add(others[2]).json()["state"] == "device_limit"  # three devices already
    devices = client.get("/v1/me/trial/devices", headers=who.headers).json()
    replace = add(others[2], replaces=devices[0]["id"])
    assert replace.json()["state"] == "device_authorized"
    again = add(_install(), replaces=devices[1]["id"])
    assert again.status_code == 409 and again.json()["code_reason"] == "REPLACEMENT_LIMIT"
    assert client.delete(f"/v1/me/trial/devices/{devices[1]['id']}", headers=who.headers).status_code == 204
    assert add(_install()).json()["state"] == "device_authorized"


def test_paid_access_is_never_blocked_by_a_device_decision(client: TestClient) -> None:
    who, install = _user(client), _install()
    finance = _user(client, ["finance"], mfa=True)
    with get_sessionmaker()() as db:
        email = db.execute(text("select email from app_user where id = :u"), {"u": str(who.id)}).scalar()
    g = client.post(
        "/v1/admin/entitlements",
        headers=finance.headers,
        json={"email": email, "source": "pilot", "days": 7, "written_units": 0, "reason": "Fixture pilot access"},
    )
    assert g.status_code == 201, g.text
    assert _claim(client, who, install, verdict="consumed").json()["state"] == "paid_active"


def test_a_support_reviewer_can_issue_a_bounded_shared_device_exception(client: TestClient) -> None:
    who, install = _user(client), _install()
    assert client.post("/v1/me/trial", headers=who.headers).status_code == 200
    with get_sessionmaker()() as db:
        email = db.execute(text("select email from app_user where id = :u"), {"u": str(who.id)}).scalar()
    body = {"email": email, "surface": "android", "days": 7, "reason": "Fixture: family phone, private review"}
    assert (
        client.post("/v1/staff/trial/exceptions", headers=_user(client, ["support"]).headers, json=body).status_code
        == 403
    )
    reviewer = _user(client, ["support"], mfa=True)
    assert client.post("/v1/staff/trial/exceptions", headers=reviewer.headers, json=body).status_code == 201
    r = client.post(
        "/v1/me/trial/devices",
        headers={**who.headers, **_native(install)},
        json={"surface": "android", "proof": {"fixture_verdict": "consumed"}},
    ).json()
    assert r["state"] == "device_authorized"
    devices = client.get("/v1/me/trial/devices", headers=who.headers).json()
    assert any(d["method"] == "exception" for d in devices) and _grants(who) == 1


def test_prior_paid_customers_get_no_claim(client: TestClient) -> None:
    who = _user(client)
    with get_sessionmaker()() as db:
        db.execute(
            text(
                "insert into entitlement (id, user_id, source, product_code, scope, starts_at, ends_at, status, "
                "written_units, reason) values (gen_random_uuid(), :u, 'paid', 'platform', '{}'::jsonb, "
                "now() - interval '60 days', now() - interval '30 days', 'active', 0, 'fixture past purchase')"
            ),
            {"u": str(who.id)},
        )
        db.commit()
    assert _claim(client, who, _install()).json()["state"] == "prior_paid" and _grants(who) == 0


def test_simultaneous_claims_for_one_account_create_one_grant(client: TestClient) -> None:
    who = _user(client)
    barrier = threading.Barrier(4)

    def go(_: int) -> str:
        barrier.wait()
        return str(_claim(client, who, _install()).json()["state"])

    with ThreadPoolExecutor(max_workers=4) as pool:
        states = sorted(pool.map(go, range(4)))
    assert _grants(who) == 1
    assert states.count("granted") == 1 and set(states) <= {"granted", "device_authorized", "device_limit"}
