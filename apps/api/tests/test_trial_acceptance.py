"""P14.S8.T3 (TRIAL-MATRIX-01): isolated protocol paths of the trial acceptance matrix not covered elsewhere.

`docs/project/TRIAL_ACCEPTANCE_MATRIX.md` lists every scenario (AC29-AC44, AC55, AC64-AC66), the tests that cover its
protocol path and the real-device or payment-sandbox evidence it still needs. Device evidence here comes from the
development fixture adapter: it exercises the decision table and proves nothing about real device recall (B07/B08).
Accounts, grants and purchases are labelled technical fixtures.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.access import trial_devices
from tests.test_attempts import _op
from tests.test_trial_claims import _claim, _grants, _install, _native, _user


def _signed_in_again(client: TestClient, email: str) -> dict[str, str]:
    """A fresh sign-in for the same account, as after signing out."""
    tok = client.post("/v1/dev-auth/token", json={"email": email, "password": "correct-horse-battery", "mfa": False})
    assert tok.status_code == 200, tok.text
    return {"Authorization": f"Bearer {tok.json()['access_token']}"}


def _provider_down(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every call to the device-evidence provider is recorded and fails, as in an outage or a slow provider."""
    calls: list[str] = []

    def down(self: Any, proof: dict[str, Any]) -> Any:
        calls.append(str(proof))
        raise TimeoutError("device provider timed out")

    monkeypatch.setattr(trial_devices.FixtureProvider, "evaluate", down)
    monkeypatch.setattr(trial_devices.FixtureProvider, "mark_consumed", down)
    return calls


def test_signing_in_again_or_switching_class_exam_or_stream_never_resets_the_trial(client: TestClient) -> None:
    """AC31 (logout) and AC42 (switching course or exam): one grant with its original dates."""
    who = _user(client)
    first = client.post("/v1/me/trial", headers=who.headers).json()["trial"]
    assert first["status"] == "active"
    again = _signed_in_again(client, who.email)
    profiles = (
        {"grade": 11, "stream": "pre_medical", "subjects": ["biology", "chemistry"], "target_exams": ["mdcat"]},
        {"grade": 12, "stream": "pre_engineering", "subjects": ["physics", "mathematics"], "target_exams": ["ecat"]},
    )
    for profile in profiles:
        assert client.put("/v1/me/profile", headers=again, json=profile).status_code == 200
        retried = client.post("/v1/me/trial", headers=again).json()["trial"]
        assert (retried["status"], retried["granted_at"], retried["ends_at"]) == (
            "active",
            first["granted_at"],
            first["ends_at"],
        )
    # Moving to the app on a clean device authorizes that device under the same grant; no second trial.
    native = _claim(client, who, _install()).json()
    assert native["state"] == "device_authorized" and native["ends_at"] == first["ends_at"]
    assert _grants(who) == 1


def test_a_provider_outage_keeps_existing_trial_access(
    client: TestClient, physics: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC39: an outage is never a reason to take away access already granted."""
    who, install, key = _user(client), _install(), uuid.uuid4().hex
    granted = _claim(client, who, install, key=key).json()
    assert granted["state"] == "granted"
    calls = _provider_down(monkeypatch)
    native = {**who.headers, **_native(install)}
    access = client.get("/v1/me/access", headers=native).json()
    assert access["has_access"] is True and access["device_state"] is None
    assert access["trial"]["ends_at"] == granted["ends_at"]
    for k in (key, uuid.uuid4().hex):  # a retried claim, and a fresh one from the same app, keep the original grant
        again = _claim(client, who, install, key=k).json()
        assert again["state"] in ("granted", "device_authorized") and again["ends_at"] == granted["ends_at"]
    lesson_or_test = client.post(
        "/v1/practice/forms",
        headers={**native, "Idempotency-Key": uuid.uuid4().hex},
        json={"grade": 11, "subject": "physics", "chapter_ids": [physics["chapter"]], "question_count": 2},
    )
    assert lesson_or_test.status_code == 201, lesson_or_test.text
    assert calls == [] and _grants(who) == 1


def test_answer_saving_and_submission_never_wait_for_device_recall(
    client: TestClient, physics: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC44: a slow or failing provider can't hold up a learner's answers; device checks read our own records."""
    who, install = _user(client), _install()
    assert _claim(client, who, install).json()["state"] == "granted"
    calls = _provider_down(monkeypatch)
    native = {**who.headers, **_native(install)}
    form = client.post(
        "/v1/practice/forms",
        headers={**native, "Idempotency-Key": uuid.uuid4().hex},
        json={"grade": 11, "subject": "physics", "chapter_ids": [physics["chapter"]], "question_count": 2},
    )
    assert form.status_code == 201, form.text
    attempt = client.post(f"/v1/practice/forms/{form.json()['id']}/attempt", headers=native)
    assert attempt.status_code == 200, attempt.text
    a = attempt.json()["id"]
    saved = client.post(f"/v1/attempts/{a}/answers", headers=native, json={"ops": [_op(1, 1, "o1"), _op(2, 1, "o2")]})
    assert saved.status_code == 200, saved.text
    done = client.post(
        f"/v1/attempts/{a}/submit", headers=native, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert done.status_code == 200, done.text
    # An unauthorized install of the same account is refused by our own records, still without calling the provider.
    other = {**who.headers, **_native(_install())}
    refused = client.post(
        "/v1/practice/forms",
        headers={**other, "Idempotency-Key": uuid.uuid4().hex},
        json={"grade": 11, "subject": "physics", "chapter_ids": [physics["chapter"]], "question_count": 2},
    )
    assert refused.status_code == 403 and refused.json()["title"] == "DEVICE_AUTHORIZATION_REQUIRED"
    assert calls == []


def test_a_pending_claim_is_rechecked_against_the_current_account(client: TestClient) -> None:
    """AC64: a suspended account can't complete its claim; once reinstated, the current claim completes once. A
    refunded purchase is still paid history, so it can't mint an introductory trial."""
    who, install, key = _user(client), _install(), uuid.uuid4().hex
    admin = _user(client, ["owner_admin"], mfa=True)
    lost = _claim(client, who, install, key=key, fixture_mark="lost").json()
    assert lost["claim_status"] == "MARK_UNKNOWN" and _grants(who) == 0
    reason = {"reason": "Fixture: account check"}
    assert client.post(f"/v1/admin/users/{who.id}/suspend", headers=admin.headers, json=reason).status_code == 200
    assert _claim(client, who, install, key=key).status_code in (401, 403) and _grants(who) == 0
    assert client.post(f"/v1/admin/users/{who.id}/reinstate", headers=admin.headers, json=reason).status_code == 200
    done = _claim(client, who, install, key=key).json()
    assert done["state"] == "granted" and _grants(who) == 1
    assert _claim(client, who, install, key=key).json()["ends_at"] == done["ends_at"]  # retries keep the dates

    refunded = _user(client)
    with get_sessionmaker()() as db:
        db.execute(
            text(
                "insert into entitlement (id, user_id, source, product_code, scope, starts_at, ends_at, status, "
                "written_units, reason) values (gen_random_uuid(), :u, 'paid', 'platform', '{}'::jsonb, "
                "now() - interval '20 days', now() + interval '10 days', 'refunded', 0, 'fixture refunded purchase')"
            ),
            {"u": str(refunded.id)},
        )
        db.commit()
    assert _claim(client, refunded, _install()).json()["state"] == "prior_paid"
    web = client.post("/v1/me/trial", headers=refunded.headers)
    assert web.status_code in (200, 409) and _grants(refunded) == 0
