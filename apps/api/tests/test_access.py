"""Trial, entitlements and the written allowance ledger (§16, P14.S5, §20.13.4). Fixture accounts only."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.access.models import Entitlement, TrialGrant
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _form, _map, _png, _seal, _upload


def _fresh(client: TestClient) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, [])


def _access(client: TestClient, who: Staff) -> dict[str, Any]:
    return dict(client.get("/v1/me/access", headers=who.headers).json())


def _shift_trial(user_id: uuid.UUID, days: float) -> None:
    with get_sessionmaker()() as db:
        db.execute(
            text(
                "update entitlement set starts_at = starts_at + make_interval(days => :d), "
                "ends_at = ends_at + make_interval(days => :d) where user_id = :u"
            ),
            {"d": days, "u": user_id},
        )
        db.execute(
            text(
                "update trial_grant set granted_at = granted_at + make_interval(days => :d), "
                "ends_at = ends_at + make_interval(days => :d) where user_id = :u"
            ),
            {"d": days, "u": user_id},
        )
        db.commit()


def test_new_starts_need_an_active_plan(client: TestClient, published_written: dict[str, Any]) -> None:
    who = _fresh(client)
    a = _access(client, who)
    assert a["has_access"] is False and a["trial"]["status"] == "available" and a["trial"]["eligible"]
    r = client.post(
        "/v1/practice/forms",
        headers={**who.headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"grade": 11, "subject": "physics", "chapter_ids": [str(uuid.uuid4())], "question_count": 1},
    )
    assert r.status_code == 403 and r.json()["title"] == "ACCESS_REQUIRED" and r.json()["trial_available"] is True
    w = _form(client, who, published_written["chapter"])
    assert w.status_code == 403 and w.json()["title"] == "ACCESS_REQUIRED"


def test_one_trial_per_account_with_exact_dates(client: TestClient) -> None:
    who = _fresh(client)
    first = client.post("/v1/me/trial", headers=who.headers).json()
    assert first["has_access"] and first["trial"]["status"] == "active"
    granted, ends = first["trial"]["granted_at"], first["trial"]["ends_at"]
    with get_sessionmaker()() as db:
        grant = db.scalar(select(TrialGrant).where(TrialGrant.user_id == who.id))
        assert grant is not None and grant.ends_at - grant.granted_at == timedelta(days=30)
    again = client.post("/v1/me/trial", headers=who.headers).json()
    assert (again["trial"]["granted_at"], again["trial"]["ends_at"]) == (granted, ends)  # retries keep original dates
    assert len(again["entitlements"]) == 1 and again["written_allowance"]["granted"] == 10

    _shift_trial(who.id, -31)  # the trial period has passed
    ended = _access(client, who)
    assert ended["has_access"] is False and ended["trial"]["status"] == "ended"
    assert client.post("/v1/me/trial", headers=who.headers).json()["trial"]["ends_at"] != ends  # shifted, not reset
    with get_sessionmaker()() as db:
        assert db.scalar(select(text("count(*)")).select_from(TrialGrant).where(TrialGrant.user_id == who.id)) == 1


def test_prior_paid_customers_get_no_trial(client: TestClient, db: Session) -> None:
    who = _fresh(client)
    db.add(
        Entitlement(
            user_id=who.id,
            source="paid",
            starts_at=db.execute(text("select now() - interval '60 days'")).scalar_one(),
            ends_at=db.execute(text("select now() - interval '30 days'")).scalar_one(),
            reason="fixture: expired paid plan",
        )
    )
    db.commit()
    a = _access(client, who)
    assert a["trial"]["status"] == "not_eligible" and not a["trial"]["eligible"]
    assert client.post("/v1/me/trial", headers=who.headers).status_code == 409


def test_staff_grants_need_permission_and_mfa(client: TestClient, db: Session) -> None:
    learner = _fresh(client)
    finance = Staff(client, db, ["finance"], mfa=True)
    finance_no_mfa = Staff(client, db, ["finance"])
    body = {
        "email": learner.email,
        "source": "scholarship",
        "days": 30,
        "written_units": 4,
        "reason": "Fixture scholarship grant",
    }
    assert client.post("/v1/admin/entitlements", headers=learner.headers, json=body).status_code == 403
    assert client.post("/v1/admin/entitlements", headers=finance_no_mfa.headers, json=body).status_code == 403
    granted = client.post("/v1/admin/entitlements", headers=finance.headers, json=body)
    assert granted.status_code == 201
    assert _access(client, learner)["has_access"] is True
    revoked = client.post(
        f"/v1/admin/entitlements/{granted.json()['id']}/revoke",
        headers=finance.headers,
        json={"reason": "Fixture: granted in error"},
    )
    assert revoked.json()["status"] == "revoked" and _access(client, learner)["has_access"] is False


def _start_written(client: TestClient, who: Staff, chapter: str) -> Any:
    f = _form(client, who, chapter)
    if f.status_code != 201:
        return f
    return client.post(f"/v1/written/forms/{f.json()['id']}/attempt", headers=who.headers)


def test_written_allowance_ledger(client: TestClient, published_written: dict[str, Any]) -> None:
    who = _fresh(client)
    client.post("/v1/me/trial", headers=who.headers)
    chapter = published_written["chapter"]
    a = _start_written(client, who, chapter).json()
    al = _access(client, who)["written_allowance"]
    assert (al["reserved"], al["available"]) == (1, 9)  # one short question reserved at start
    page = _upload(client, who, a["id"], _png(seed=41)).json()["page"]["id"]
    m = _map(client, who, a, {"1:a": {"pages": [page]}, "1:b": {"unanswered": True}}).json()
    assert _seal(client, who, a["id"], m["manifest_revision"]).status_code == 200
    al = _access(client, who)["written_allowance"]
    assert (al["reserved"], al["accepted"], al["available"]) == (0, 1, 9)

    # Releasing marks consumes once; saving a draft mark doesn't.
    with get_sessionmaker()() as db:
        reviewer = Staff(client, db, ["subject_reviewer"], {"grades": [12], "subjects": ["chemistry"]})
    case = next(
        c
        for c in client.get("/v1/studio/written/queue", headers=reviewer.headers).json()
        if c["reference"] == a["id"][:8]
    )
    client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)
    awards = {"1": {"a1": {"units": 100}, "b1": {"units": 0}, "b2": {"units": 0}}}
    client.post(
        f"/v1/studio/written/cases/{case['id']}/decision",
        headers=reviewer.headers,
        json={"expected_version": 0, "awards": awards, "release": False},
    )
    assert _access(client, who)["written_allowance"]["consumed"] == 0
    client.post(
        f"/v1/studio/written/cases/{case['id']}/decision",
        headers=reviewer.headers,
        json={"expected_version": 1, "awards": awards, "release": True},
    )
    al = _access(client, who)["written_allowance"]
    assert (al["accepted"], al["consumed"], al["available"]) == (0, 1, 9)

    # An unsealed attempt that expires returns its whole reservation.
    b = _start_written(client, who, chapter).json()
    assert _access(client, who)["written_allowance"]["available"] == 8
    with get_sessionmaker()() as db:
        db.execute(
            text("update written_attempt set upload_cutoff_at = now() - interval '1 second' where id = :i"),
            {"i": b["id"]},
        )
        db.commit()
    client.get(f"/v1/written-attempts/{b['id']}", headers=who.headers)  # expires under the lock
    assert _access(client, who)["written_allowance"]["available"] == 9


def test_open_permit_and_allowance_limits(client: TestClient, db: Session, published_written: dict[str, Any]) -> None:
    learner = _fresh(client)
    finance = Staff(client, db, ["finance"], mfa=True)
    client.post(
        "/v1/admin/entitlements",
        headers=finance.headers,
        json={
            "email": learner.email,
            "source": "pilot",
            "days": 7,
            "written_units": 1,
            "reason": "Fixture pilot with one unit",
        },
    )
    chapter = published_written["chapter"]
    assert _start_written(client, learner, chapter).status_code == 200
    exhausted = _start_written(client, learner, chapter)
    assert exhausted.status_code == 403 and exhausted.json()["title"] == "ALLOWANCE_EXHAUSTED"
    # With enough units, a third concurrent open written test is still refused.
    roomy = _fresh(client)
    client.post("/v1/me/trial", headers=roomy.headers)
    assert _start_written(client, roomy, chapter).status_code == 200
    assert _start_written(client, roomy, chapter).status_code == 200
    third = _start_written(client, roomy, chapter)
    assert third.status_code == 403 and "at most 2" in third.json()["detail"]


def test_cors_allows_the_client_header_used_by_native_trial_activation(client: TestClient) -> None:
    pre = client.options(
        "/v1/me/trial",
        headers={
            "Origin": "http://localhost:8190",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-portal-client",
        },
    )
    assert pre.status_code == 200
    assert "x-portal-client" in pre.headers["access-control-allow-headers"].lower()
