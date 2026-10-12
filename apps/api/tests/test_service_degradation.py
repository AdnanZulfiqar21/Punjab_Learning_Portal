"""P19.S3.T2 (DEGRADATION-01): provider outages. Identity, email, media storage and scanning, device attestation and
payment providers are made to fail; each failure must be explicit (a clear state or a 503 that says when to retry),
never recorded as the provider's success, and must leave core records as they were, so a retry succeeds once the
provider is back. Outages are simulated with monkeypatched adapters; fixture accounts and synthetic files only."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from portal_api.config import get_settings
from portal_api.db import get_sessionmaker
from portal_api.errors import StorageUnavailable
from portal_api.main import app
from portal_api.modules.access import trial_devices
from portal_api.modules.content import assets, uploads
from portal_api.modules.identity import tokens
from portal_api.modules.identity.models import AppUser
from portal_api.modules.notifications import delivery
from portal_api.modules.system import scanning
from portal_api.modules.written import storage
from tests.test_assets import BIO, _asset
from tests.test_assets import _upload as _asset_upload
from tests.test_content_workflow import Staff
from tests.test_data_minimisation import _jpeg_with_gps
from tests.test_media_uploads import FIXTURE, MB, _chunk, _lecture
from tests.test_media_uploads import _start as _start_media
from tests.test_notifications import _deliveries, _due_now, _emit, _no_quiet, _user
from tests.test_support_attachments import _attach, _staff, _ticket
from tests.test_trial_claims import _claim, _grants, _install
from tests.test_written_attempts import _png, _start, _upload


def _retryable(r: Any, reason: str) -> None:
    assert r.status_code == 503, r.text
    assert r.json()["code_reason"] == reason, r.text
    assert int(r.headers["retry-after"]) > 0  # says when to try again


# ------------------------------------------------------------------ identity
def test_an_identity_provider_outage_is_retryable_not_a_sign_out(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    learner = Staff(client, get_sessionmaker()(), [])
    session = client.post(
        "/v1/sessions", headers=learner.headers, json={"kind": "native", "device_label": "Fixture laptop"}
    )
    assert session.status_code == 201, session.text
    app_session = {"Authorization": f"Bearer {session.json()['session_token']}"}

    issuer = "https://idp.fixture.invalid/pool"
    monkeypatch.setattr(
        tokens, "get_settings", lambda: get_settings().model_copy(update={"oidc_issuer": issuer, "oidc_audience": "a1"})
    )

    class DownJwks:
        def get_signing_key_from_jwt(self, _token: str) -> Any:
            raise jwt.PyJWKClientConnectionError("Fail to fetch data from the url, err: timed out")

    monkeypatch.setattr(tokens, "_jwks_client", lambda _url: DownJwks())
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    subject = f"fixture-{uuid.uuid4().hex}"
    claims = {"iss": issuer, "sub": subject, "iat": now, "exp": now + 300, "client_id": "a1", "token_use": "access"}
    r = client.get("/v1/me", headers={"Authorization": f"Bearer {jwt.encode(claims, key, 'RS256')}"})
    _retryable(r, "IDENTITY_UNAVAILABLE")  # not 401: the learner's sign-in is fine, the provider is down
    with get_sessionmaker()() as db:
        assert db.scalar(select(AppUser).where(AppUser.subject == subject)) is None  # no account made on a guess
    assert client.get("/v1/me", headers=app_session).status_code == 200  # portal sessions don't need the provider

    class UnknownKey:
        def get_signing_key_from_jwt(self, _token: str) -> Any:
            raise jwt.PyJWKClientError("Unable to find a signing key that matches")

    monkeypatch.setattr(tokens, "_jwks_client", lambda _url: UnknownKey())
    assert (
        client.get("/v1/me", headers={"Authorization": f"Bearer {jwt.encode(claims, key, 'RS256')}"}).status_code == 401
    )


# ------------------------------------------------------------------ email
def test_an_email_sender_that_is_not_wired_up_never_counts_as_sent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = _user(client)
    _no_quiet(client, a, push_enabled=False)
    assert _emit(a, "support.reply", {"subject": "Fixture"}, f"degrade-{uuid.uuid4().hex}")
    # A provider name the code doesn't implement yet (e.g. a future real sender) must not fall through to "sent".
    fake = get_settings().model_copy(update={"notification_email_adapter": "ses"})
    monkeypatch.setattr(delivery, "get_settings", lambda: fake)
    _due_now(a)
    with get_sessionmaker()() as db:
        delivery.deliver_due(db, limit=100_000)
    email = [d for d in _deliveries(a) if d.channel == "email"]
    assert email and all(d.status != "sent" for d in email)
    assert all(d.status == "unavailable" and "not implemented" in (d.last_error or "") for d in email)


# ------------------------------------------------------------------ media: scanning and storage
def test_a_scanner_outage_says_when_to_retry(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    learner = _staff(client, [])
    ticket = _ticket(client, learner)
    monkeypatch.setattr(scanning, "scan", lambda data: scanning.Verdict("unavailable", None))
    _retryable(_attach(client, learner, ticket["id"], _png()), "SCANNER_UNAVAILABLE")


def test_a_storage_outage_is_retryable_and_leaves_no_records(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    who = _staff(client, [])
    client.post("/v1/me/trial", headers=who.headers)
    attempt = _start(client, who, published_written["chapter"])
    store = storage.get_store()
    before = {k for k, _ in store.list_objects()}

    def disk_full(key: str, data: bytes) -> Any:
        raise storage.EvidenceStoreUnavailable()  # what the store raises when it can't write (tested below)

    monkeypatch.setattr(store, "put", disk_full)
    _retryable(_upload(client, who, attempt["id"], _png(seed=41)), "STORAGE_UNAVAILABLE")
    learner = _staff(client, [])
    ticket = _ticket(client, learner)
    _retryable(_attach(client, learner, ticket["id"], _png(seed=42)), "STORAGE_UNAVAILABLE")

    def not_connected() -> Any:
        raise storage.EvidenceStoreUnavailable("Private object storage isn't connected yet (BLOCKERS B03).")

    monkeypatch.setattr(storage, "get_store", not_connected)
    _retryable(_upload(client, who, attempt["id"], _png(seed=41)), "STORAGE_UNAVAILABLE")
    monkeypatch.undo()

    assert {k for k, _ in store.list_objects()} == before  # nothing half-stored
    got = client.get(f"/v1/written-attempts/{attempt['id']}", headers=who.headers).json()
    assert got["pages"] == []  # no page rows from the failed uploads
    assert _upload(client, who, attempt["id"], _png(seed=41)).status_code in (200, 201)  # the retry works


def test_an_asset_storage_failure_leaves_no_version_and_no_orphan_file(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    author = Staff(client, db, ["content_author"], BIO)
    a = _asset(client, author, "image", "Fixture outage diagram")
    written: list[str] = []
    real_write = assets._write

    def fail_on_delivery(key: str, data: bytes) -> None:
        if key.endswith("/delivery"):
            raise StorageUnavailable()  # what _write raises on a disk error (tested below)
        real_write(key, data)
        written.append(key)

    monkeypatch.setattr(assets, "_write", fail_on_delivery)
    _retryable(_asset_upload(client, author, a["id"], _jpeg_with_gps()), "STORAGE_UNAVAILABLE")
    assert written and not any((assets._root() / key).exists() for key in written)  # the master was removed again
    with get_sessionmaker()() as fresh:
        count = fresh.execute(
            text("select count(*) from content_asset_version where asset_id = :a"), {"a": a["id"]}
        ).scalar_one()
    assert count == 0
    monkeypatch.undo()
    assert _asset_upload(client, author, a["id"], _jpeg_with_gps()).status_code == 201


def test_the_local_stores_turn_disk_errors_into_retryable_outages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = storage.LocalEvidenceStore(tmp_path / "evidence")
    (tmp_path / "evidence").rmdir()
    (tmp_path / "evidence").write_bytes(b"not a directory")  # the volume is gone or unwritable
    with pytest.raises(storage.EvidenceStoreUnavailable):
        store.put("attempt/file/original", b"fixture")
    blocked = tmp_path / "assets-volume"
    blocked.write_bytes(b"not a directory")
    monkeypatch.setattr(assets, "_root", lambda: blocked)
    with pytest.raises(StorageUnavailable):
        assets._write("asset/version/master", b"fixture")


def test_a_failed_chunk_write_keeps_the_resume_point(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    team, lecture = _lecture(client, db)
    author = team["author"]
    up = _start_media(client, author, lecture, FIXTURE).json()
    assert _chunk(client, author, up["id"], 0, FIXTURE[:MB]).json()["received"] == MB
    monkeypatch.setattr(uploads, "_part", lambda _id: Path("/nonexistent-volume/portal/upload.part"))
    _retryable(_chunk(client, author, up["id"], MB, FIXTURE[MB : 2 * MB]), "STORAGE_UNAVAILABLE")
    monkeypatch.undo()
    state = client.get(f"/v1/studio/uploads/{up['id']}", headers=author.headers).json()
    assert state["state"] == "uploading" and state["received"] == MB  # resume from where it was
    assert _chunk(client, author, up["id"], MB, FIXTURE[MB : 2 * MB]).json()["received"] == 2 * MB


# ------------------------------------------------------------------ device attestation
def _claim_row(user_id: uuid.UUID) -> tuple[str, dict[str, Any]]:
    with get_sessionmaker()() as db:
        row = db.execute(
            text("select status, evidence from trial_claim where user_id = :u order by created_at desc limit 1"),
            {"u": str(user_id)},
        ).one()
    return row[0], row[1] or {}


def test_an_attestation_outage_keeps_the_claim_and_grants_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    who, install, key = _staff(client, []), _install(), uuid.uuid4().hex

    def down(self: Any, proof: dict[str, Any]) -> Any:
        raise ConnectionError("attestation provider timed out")

    monkeypatch.setattr(trial_devices.FixtureProvider, "evaluate", down)
    r = _claim(client, who, install, key=key)
    assert r.status_code == 200 and r.json()["state"] == "verification_pending", r.text
    status, evidence = _claim_row(who.id)
    assert status == "PENDING_VERIFICATION" and evidence["verdict"] == "unknown"
    assert evidence["detail"].startswith("provider_error")  # recorded as an outage, never as clean
    assert _grants(who) == 0
    monkeypatch.undo()
    assert _claim(client, who, install, key=key).json()["state"] == "granted"  # the same claim, once it's back
    assert _grants(who) == 1


def test_a_failed_marker_write_is_recovered_on_the_same_claim(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    who, install, key = _staff(client, []), _install(), uuid.uuid4().hex
    seen: list[str] = []

    def write_fails(self: Any, proof: dict[str, Any]) -> Any:
        seen.append(_claim_row(who.id)[0])  # what another process would see while the remote write is in flight
        raise TimeoutError("marker write timed out")

    monkeypatch.setattr(trial_devices.FixtureProvider, "mark_consumed", write_fails)
    r = _claim(client, who, install, key=key)
    assert r.json()["state"] == "verification_pending", r.text
    assert seen == ["MARK_PENDING"]  # the claim was saved before the remote write, so a crash can't lose it
    assert _claim_row(who.id)[0] == "MARK_UNKNOWN" and _grants(who) == 0
    monkeypatch.undo()
    # The provider now remembers this device (our own marker). The same claim recovers instead of reading it as reuse.
    again = _claim(client, who, install, verdict="consumed", key=key).json()
    assert again["state"] == "granted" and _grants(who) == 1


def test_parallel_claims_while_the_lock_is_released_mark_each_device_once(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The claim is committed before the remote marker write (releasing the account lock), so parallel claims for the
    same account can interleave there. Still one grant, and each device's marker is written exactly once."""
    who = _staff(client, [])
    marks: dict[str, int] = {}
    lock = threading.Lock()
    real = trial_devices.FixtureProvider.mark_consumed

    def counting(self: Any, proof: dict[str, Any]) -> Any:
        with lock:
            marks[proof["device"]] = marks.get(proof["device"], 0) + 1
        return real(self, proof)

    monkeypatch.setattr(trial_devices.FixtureProvider, "mark_consumed", counting)
    barrier = threading.Barrier(4)

    def go(i: int) -> str:
        barrier.wait()
        return str(_claim(client, who, _install(), device=f"d{i}").json()["state"])

    with ThreadPoolExecutor(max_workers=4) as pool:
        states = list(pool.map(go, range(4)))
    assert _grants(who) == 1 and states.count("granted") == 1, states
    assert set(states) <= {"granted", "device_authorized", "device_limit"}, states
    assert all(n == 1 for n in marks.values())  # no device marked twice
    assert len(marks) == sum(s in ("granted", "device_authorized") for s in states)


# ------------------------------------------------------------------ payment
def test_no_payment_success_can_be_fabricated(client: TestClient, db: Session) -> None:
    spec = app.openapi()
    words = ("payment", "checkout", "webhook", "purchase", "callback")
    assert not [p for p in spec["paths"] if any(w in p.lower() for w in words)]  # no provider route exists yet (B06)
    finance = Staff(client, db, ["finance"], None, mfa=True)
    learner = Staff(client, db, [])
    paid = {"email": learner.email, "source": "paid", "days": 30, "written_units": 0, "reason": "Fixture paid grant"}
    assert client.post("/v1/admin/entitlements", headers=finance.headers, json=paid).status_code == 422
    providers = {i["key"]: i for i in client.get("/v1/ops/integrations", headers=_operator(client, db)).json()}
    payment = [i for k, i in providers.items() if "payment" in k]
    assert payment and all(i["mode"] == "unavailable" for i in payment)


def _operator(client: TestClient, db: Session) -> dict[str, str]:
    return Staff(client, db, ["platform_operator"], None, mfa=True).headers
