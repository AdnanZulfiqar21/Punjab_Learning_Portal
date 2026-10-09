"""P15.S1 notifications: idempotent events, categories and opt-outs, inbox, preferences (timezone, quiet hours),
queued email/push delivery with caps, retries and honest unavailable channels, and the emitters wired so far.
Real PostgreSQL; technical fixtures only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from portal_api.db import get_sessionmaker
from portal_api.modules.notifications import delivery, service
from portal_api.modules.notifications.models import NotificationDelivery, NotificationPreference
from tests.test_content_workflow import Staff
from tests.test_rescan_corrections import _aw, _decide, _pending, _sealed, _staff


def _user(client: TestClient) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, [])


def _inbox(client: TestClient, who: Staff) -> dict[str, Any]:
    r = client.get("/v1/me/notifications", headers=who.headers)
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"
    return dict(r.json())


def _emit(who: Staff, event: str, params: dict[str, Any], key: str) -> bool:
    with get_sessionmaker()() as db:
        n = service.notify(db, who.id, event, params, dedupe_key=key, link="/account")
        db.commit()
        return n is not None


def _deliveries(who: Staff) -> list[NotificationDelivery]:
    with get_sessionmaker()() as db:
        return list(
            db.scalars(
                select(NotificationDelivery)
                .where(NotificationDelivery.user_id == who.id)
                .order_by(NotificationDelivery.created_at, NotificationDelivery.channel)
            )
        )


def _due_now(who: Staff) -> None:
    with get_sessionmaker()() as db:
        db.execute(
            text(
                "update notification_delivery set next_attempt_at = clock_timestamp() "
                "where user_id = :u and status = 'queued'"
            ),
            {"u": str(who.id)},
        )
        db.commit()


def _no_quiet(client: TestClient, who: Staff, **extra: Any) -> None:
    body = {"timezone": "UTC", "quiet_start": "00:00", "quiet_end": "00:00", **extra}
    assert client.put("/v1/me/notification-preferences", headers=who.headers, json=body).status_code == 200


# ------------------------------------------------------------------ events, categories, inbox
def test_events_are_idempotent_categorised_and_private(client: TestClient) -> None:
    a, b = _user(client), _user(client)
    assert _emit(a, "support.reply", {"subject": "Fixture"}, "k1") is True
    assert _emit(a, "support.reply", {"subject": "Fixture"}, "k1") is False  # same key: nothing new
    assert _emit(a, "content.available", {"what": "Fixture"}, "promo-1") is False  # promotional: not opted in
    inbox = _inbox(client, a)
    assert inbox["unread"] == 1 and [n["event"] for n in inbox["items"]] == ["support.reply"]
    assert inbox["items"][0]["body"] == "Support replied to “Fixture”."
    nid = inbox["items"][0]["id"]
    assert client.post(f"/v1/me/notifications/{nid}/read", headers=b.headers).status_code == 404  # not theirs
    assert client.post(f"/v1/me/notifications/{nid}/read", headers=a.headers).status_code == 204
    assert _inbox(client, a)["unread"] == 0
    # opting in to news and out of reminders changes what is recorded
    prefs = {"promotional_opt_in": True, "reminders_enabled": False}
    _no_quiet(client, a, **prefs)
    assert _emit(a, "content.available", {"what": "Fixture"}, "promo-2") is True
    assert _emit(a, "revision.reminder", {"topic": "Fixture"}, "rem-1") is False
    assert client.post("/v1/me/notifications/read-all", headers=a.headers).status_code == 204
    assert _inbox(client, a)["unread"] == 0
    with pytest.raises(ValueError):
        _emit(a, "support.reply", {}, "k-missing")  # a template never renders with missing parameters


def test_preferences_validate_timezone_and_quiet_hours(client: TestClient) -> None:
    a = _user(client)
    got = client.get("/v1/me/notification-preferences", headers=a.headers).json()
    assert (got["timezone"], got["quiet_start"], got["quiet_end"], got["promotional_opt_in"]) == (
        "Asia/Karachi",
        "22:00",
        "07:00",
        False,
    )
    bad_tz = client.put("/v1/me/notification-preferences", headers=a.headers, json={**got, "timezone": "Mars/Base"})
    assert bad_tz.status_code == 422
    bad_time = client.put("/v1/me/notification-preferences", headers=a.headers, json={**got, "quiet_start": "25:00"})
    assert bad_time.status_code == 422
    ok = client.put("/v1/me/notification-preferences", headers=a.headers, json={**got, "email_enabled": False})
    assert ok.status_code == 200 and ok.json()["email_enabled"] is False
    assert _emit(a, "support.reply", {"subject": "Fixture"}, "no-email")
    assert [d.channel for d in _deliveries(a)] == ["push"]  # email switched off: no email delivery queued


def test_quiet_hours_cross_midnight_in_the_learners_timezone() -> None:
    p = NotificationPreference(timezone="Asia/Karachi", quiet_start="22:00", quiet_end="07:00")
    late = datetime(2026, 10, 9, 18, 30, tzinfo=UTC)  # 23:30 in Karachi (UTC+5)
    assert service.quiet_until(p, late) == datetime(2026, 10, 10, 2, 0, tzinfo=UTC)  # 07:00 Karachi
    early = datetime(2026, 10, 9, 0, 30, tzinfo=UTC)  # 05:30 Karachi
    assert service.quiet_until(p, early) == datetime(2026, 10, 9, 2, 0, tzinfo=UTC)
    assert service.quiet_until(p, datetime(2026, 10, 9, 7, 0, tzinfo=UTC)) is None  # 12:00 Karachi
    same = NotificationPreference(timezone="UTC", quiet_start="13:00", quiet_end="15:00")
    assert service.quiet_until(same, datetime(2026, 10, 9, 14, 0, tzinfo=UTC)) == datetime(
        2026, 10, 9, 15, 0, tzinfo=UTC
    )
    off = NotificationPreference(timezone="UTC", quiet_start="00:00", quiet_end="00:00")
    assert service.quiet_until(off, late) is None


# ------------------------------------------------------------------ delivery
def test_delivery_sends_email_and_reports_push_honestly(client: TestClient) -> None:
    a = _user(client)
    _no_quiet(client, a)
    assert _emit(a, "support.reply", {"subject": "Fixture"}, "d1")
    with get_sessionmaker()() as db:
        delivery.deliver_due(db)
    by = {d.channel: d for d in _deliveries(a)}
    assert by["email"].status == "sent" and (by["email"].provider_ref or "").startswith("dev-outbox:")
    assert by["push"].status == "skipped" and by["push"].last_error == "no registered device"
    # a registered device without a push provider is reported, not faked
    bad = client.post("/v1/me/push-tokens", headers=a.headers, json={"token": "not-a-token-12345", "platform": "ios"})
    assert bad.status_code == 422
    token = f"ExponentPushToken[{uuid.uuid4().hex[:22]}]"
    assert (
        client.post("/v1/me/push-tokens", headers=a.headers, json={"token": token, "platform": "android"}).status_code
        == 204
    )
    assert _emit(a, "support.reply", {"subject": "Fixture"}, "d2")
    with get_sessionmaker()() as db:
        delivery.deliver_due(db)
    push = [d for d in _deliveries(a) if d.channel == "push"][-1]
    assert push.status == "unavailable" and "B07" in (push.last_error or "")
    assert client.delete("/v1/me/push-tokens", params={"token": token}, headers=a.headers).status_code == 204


def test_quiet_hours_defer_ordinary_notices_but_not_urgent_ones(client: TestClient) -> None:
    a = _user(client)
    now = datetime.now(UTC)
    start = (now - timedelta(hours=1)).strftime("%H:%M")
    end = (now + timedelta(hours=2)).strftime("%H:%M")
    assert (
        client.put(
            "/v1/me/notification-preferences",
            headers=a.headers,
            json={"timezone": "UTC", "quiet_start": start, "quiet_end": end, "push_enabled": False},
        ).status_code
        == 200
    )
    assert _emit(a, "support.reply", {"subject": "Fixture"}, "q1")  # ordinary
    assert _emit(a, "written.action_required", {"question": 1, "deadline": "tomorrow"}, "q2")  # urgent
    with get_sessionmaker()() as db:
        delivery.deliver_due(db)
    ds = _deliveries(a)
    ordinary = next(d for d in ds if not d.urgent)
    urgent = next(d for d in ds if d.urgent)
    assert urgent.status == "sent"
    assert ordinary.status == "queued" and ordinary.next_attempt_at > now + timedelta(hours=1)


def test_retries_back_off_then_stop_and_bursts_are_capped(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    a = _user(client)
    _no_quiet(client, a, push_enabled=False)
    assert _emit(a, "support.reply", {"subject": "Fixture"}, "r1")

    def broken(*_: Any) -> Any:
        raise RuntimeError("provider down")

    monkeypatch.setitem(delivery.ADAPTERS, "email", broken)
    for _ in range(delivery.MAX_ATTEMPTS):
        _due_now(a)
        with get_sessionmaker()() as db:
            delivery.deliver_due(db)
    d = _deliveries(a)[0]
    assert (d.status, d.attempts) == ("failed", delivery.MAX_ATTEMPTS) and "provider down" in (d.last_error or "")
    monkeypatch.undo()
    # a burst of ordinary notices: only the hourly cap is sent now, the rest wait
    for i in range(delivery.HOURLY_CAP + 3):
        assert _emit(a, "support.reply", {"subject": f"Fixture {i}"}, f"burst-{i}")
    with get_sessionmaker()() as db:
        delivery.deliver_due(db)
    sent = [d for d in _deliveries(a) if d.status == "sent"]
    queued = [d for d in _deliveries(a) if d.status == "queued"]
    assert len(sent) == delivery.HOURLY_CAP and len(queued) == 3


# ------------------------------------------------------------------ emitters
def test_a_released_result_and_a_requested_action_notify_the_learner_once(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1901)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    inbox = _inbox(client, learner)
    events = [n["event"] for n in inbox["items"]]
    assert sorted(events) == ["written.action_required", "written.result_released"]
    action = next(n for n in inbox["items"] if n["event"] == "written.action_required")
    assert "question 2" in action["body"] and action["link"] == f"/practice/written/{a['id']}"
    released = next(n for n in inbox["items"] if n["event"] == "written.result_released")
    assert released["body"].startswith("Some questions are still being marked.")
    # nothing in a notification reveals marks
    assert "1 /" not in released["body"] and "units" not in released["body"]


def test_a_staff_reply_notifies_the_learner_but_an_internal_note_does_not(client: TestClient) -> None:
    learner = _user(client)
    t = client.post(
        "/v1/support/tickets",
        headers=learner.headers,
        json={"category": "technical", "subject": "Fixture help", "body": "Fixture: something is wrong."},
    ).json()
    with get_sessionmaker()() as db:
        support = Staff(client, db, ["support"])
    for internal in (True, False):
        r = client.post(
            f"/v1/staff/support/tickets/{t['id']}/messages",
            headers=support.headers,
            json={"body": "Fixture reply", "internal": internal},
        )
        assert r.status_code == 200, r.text
    items = _inbox(client, learner)["items"]
    assert [n["event"] for n in items] == ["support.reply"] and items[0]["link"] == f"/help/{t['id']}"


def test_trial_ending_reminders_are_sent_once_per_trial(client: TestClient) -> None:
    from tests.test_written_attempts import _learner

    learner = _learner(client)  # started the free trial
    with get_sessionmaker()() as db:
        db.execute(
            text(
                "update entitlement set ends_at = clock_timestamp() + interval '2 days' "
                "where user_id = :u and source = 'trial'"
            ),
            {"u": str(learner.id)},
        )
        db.commit()
    delivery.trial_reminders([])
    delivery.trial_reminders([])
    items = [n for n in _inbox(client, learner)["items"] if n["event"] == "trial.ending"]
    assert len(items) == 1 and "Your free trial ends on" in items[0]["body"]


def test_production_refuses_the_development_email_adapter() -> None:
    from portal_api.config import ConfigurationError, Settings

    base = {
        "role": "production",
        "database_url": "postgresql+psycopg://u:p@db.example.invalid/portal",
        "public_api_origin": "https://api.example.invalid",
        "build_id": "abc123",
        "dev_auth_enabled": False,
        "oidc_issuer": "https://issuer.example.invalid",
        "oidc_audience": "portal",
        "evidence_store": "s3",
        "trial_device_evidence": "required",
        "trial_ref_pepper": "secret",
        "cors_origins": ["https://app.example.invalid"],
    }
    with pytest.raises(ConfigurationError, match="notification_email_adapter"):
        Settings(**base)
    Settings(**base, notification_email_adapter="none")
