"""Review of 2026-10-14 (docs/reviews/2026-10-14-pr188-review.md): the bulk import worker under takeover, bad input,
infrastructure trouble and changed authority. Real PostgreSQL, two sessions where two workers are involved.

* OCT14-02: a worker whose lease ran out and was taken over changes nothing: not the state, not the file, not the
  audit trail (also when its session still holds the batch it loaded at claim time).
* OCT14-03: a damaged, encrypted or oddly compressed workbook (or media pack manifest) fails with a reason, and the
  next batch in the queue is still processed; unexpected errors are retried after a pause and failed after
  MAX_ATTEMPTS, never looped on forever and never reported as a problem with the author's file.
* OCT14-05: a suspended or de-scoped author's queued work writes nothing new; an active, authorised author's does.

Rows are technical fixtures, not academic content.
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import AuditEvent
from portal_api.modules.content import bulk_imports, imports
from portal_api.modules.content.models import ContentImportBatch, ContentItem
from tests.test_bulk_import import _batch, _bulk, _csv, _items
from tests.test_content_import import _author, _setup
from tests.test_content_workflow import Staff


@pytest.fixture(autouse=True)
def _small_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(imports, "MAX_ROWS", 5)
    monkeypatch.setattr(bulk_imports, "CHUNK", 3)
    monkeypatch.setattr(bulk_imports, "SYNC_COMMIT_ROWS", 4)


def _row(batch_id: str) -> ContentImportBatch:
    with get_sessionmaker()() as db:
        b = db.get(ContentImportBatch, uuid.UUID(batch_id))
        assert b is not None
        db.expunge(b)
        return b


def _expire(batch_id: str) -> None:
    with get_sessionmaker()() as db:
        db.execute(
            text("update content_import_batch set lease_expires_at = now() - interval '1 second' where id = :i"),
            {"i": batch_id},
        )
        db.commit()


def _failure_audits(batch_id: str) -> int:
    with get_sessionmaker()() as db:
        return int(
            db.scalar(
                select(func.count(AuditEvent.id)).where(
                    AuditEvent.action == "content.import_failed", AuditEvent.target_id == batch_id
                )
            )
            or 0
        )


def _drain_until_idle(owner: str = "test-worker") -> None:
    with get_sessionmaker()() as db:
        bulk_imports.work(db, owner)


# ------------------------------------------------------------------ OCT14-02
def test_a_taken_over_worker_changes_nothing_while_validating(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    b = _bulk(client, author, _csv(uuid.uuid4().hex[:8], chapter, refs, 6)).json()
    sm = get_sessionmaker()
    with sm() as a_db, sm() as b_db:
        a = bulk_imports._claim(a_db, "worker-a")
        assert a is not None and str(a.batch_id) == b["id"]
        _expire(b["id"])
        taker = bulk_imports._claim(b_db, "worker-b")
        assert taker is not None and taker.batch_id == a.batch_id and taker.token != a.token
        key = _row(b["id"]).file_key
        assert key and (bulk_imports._root() / key).exists()

        # A wakes up while B holds the batch. A's session still has the batch it loaded when it claimed it.
        with pytest.raises(bulk_imports.Stop):
            bulk_imports._locked(a_db, a)
        assert bulk_imports._fail(a_db, a, "stale worker") == "stopped"
        with pytest.raises(bulk_imports.Stop):
            bulk_imports._check_rows(a_db, a)
        now = _row(b["id"])
        assert (now.status, now.lease_owner, now.failure) == ("validating", taker.token, None)
        assert (bulk_imports._root() / key).exists() and _failure_audits(b["id"]) == 0

        assert bulk_imports._check_rows(b_db, taker) == "previewed"
        assert bulk_imports._fail(a_db, a, "stale worker") == "stopped"  # still nothing, after B finished
    done = _batch(client, author, b["id"])
    assert done["status"] == "previewed" and done["failure"] is None and done["counts"] == {"create": 6}
    assert _failure_audits(b["id"]) == 0


def test_a_takeover_between_chunks_stops_the_old_worker_at_its_next_chunk(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Worker A holds the batch object in its session across chunks; between them it holds no lock, so B can take
    # over once A's lease has run out. A must notice at its next chunk, not trust what its session remembers.
    author = _author(client)
    chapter, refs = _setup()
    b = _bulk(client, author, _csv(uuid.uuid4().hex[:8], chapter, refs, 8)).json()
    real_actor, calls, taken = bulk_imports._actor, [], {}
    sm = get_sessionmaker()
    with sm() as a_db, sm() as b_db:
        a = bulk_imports._claim(a_db, "worker-a")
        assert a is not None

        def takeover_before_second_chunk(db: Any, user_id: uuid.UUID) -> Any:
            calls.append(1)
            if len(calls) == 2:  # A stored rows 1-3 and is about to start rows 4-6
                _expire(b["id"])
                taken["claim"] = bulk_imports._claim(b_db, "worker-b")
            return real_actor(db, user_id)

        monkeypatch.setattr(bulk_imports, "_actor", takeover_before_second_chunk)
        with pytest.raises(bulk_imports.Stop):
            bulk_imports._check_rows(a_db, a)
        monkeypatch.setattr(bulk_imports, "_actor", real_actor)
        assert _row(b["id"]).rows_checked == 3  # A wrote nothing after the takeover
        assert bulk_imports._check_rows(b_db, taken["claim"]) == "previewed"
    done = _batch(client, author, b["id"])
    assert done["counts"] == {"create": 8} and [r["row"] for r in done["rows"]] == list(range(1, 9))


def test_a_taken_over_worker_cannot_fail_a_finished_commit(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]
    b = _bulk(client, author, _csv(run, chapter, refs, 6)).json()
    _drain_until_idle()
    assert client.post(f"/v1/studio/imports/{b['id']}/commit", headers=author.headers).json()["status"] == "committing"
    sm = get_sessionmaker()
    with sm() as a_db, sm() as b_db:
        a = bulk_imports._claim(a_db, "worker-a")
        assert a is not None and a.status == "committing"
        _expire(b["id"])
        taker = bulk_imports._claim(b_db, "worker-b")
        assert taker is not None
        assert bulk_imports._commit_rows(b_db, taker) == "committed"
        with pytest.raises(bulk_imports.Stop):
            bulk_imports._commit_rows(a_db, a)
        assert bulk_imports._fail(a_db, a, "stale worker") == "stopped"
    assert _batch(client, author, b["id"])["status"] == "committed"
    assert _items(f"BULK-{run}-") == 6 and _failure_audits(b["id"]) == 0


# ------------------------------------------------------------------ OCT14-03
def _stored_template() -> bytes:
    """The real template, re-packed without compression, so single bytes can be changed predictably."""
    src = zipfile.ZipFile(io.BytesIO(imports.xlsx_template(imports.CSV_COLUMNS)))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as out:
        for info in src.infolist():
            out.writestr(info.filename, src.read(info.filename))
    return buf.getvalue()


def _patch_member(
    data: bytes, name: str, *, flip_byte: bool = False, flags: int = 0, method: int | None = None
) -> bytes:
    """Damage one member: flip a byte of its stored data (CRC no longer matches), set general-purpose flag bits
    (bit 0 = encrypted) or name another compression method, in both its local header and the central directory."""
    out = bytearray(data)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        info = z.getinfo(name)
    local = info.header_offset
    name_len = int.from_bytes(out[local + 26 : local + 28], "little")
    extra_len = int.from_bytes(out[local + 28 : local + 30], "little")
    if flip_byte:
        out[local + 30 + name_len + extra_len + 2] ^= 0x20
    central = out.find(b"PK\x01\x02", 0)
    while central != -1:
        n = int.from_bytes(out[central + 28 : central + 30], "little")
        if out[central + 46 : central + 46 + n] == name.encode():
            break
        central = out.find(b"PK\x01\x02", central + 4)
    assert central != -1
    for at, flag_at, method_at in ((local, 6, 8), (central, 8, 10)):
        if flags:
            out[at + flag_at] |= flags
        if method is not None:
            out[at + method_at : at + method_at + 2] = method.to_bytes(2, "little")
    return bytes(out)


def test_damaged_workbooks_fail_with_a_reason_and_the_queue_goes_on(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    good = _stored_template()
    variants = {
        "crc": _patch_member(good, "xl/workbook.xml", flip_byte=True),
        "encrypted": _patch_member(good, "xl/workbook.xml", flags=0x1),
        "compression": _patch_member(good, "xl/workbook.xml", method=99),
    }
    bad = {k: _bulk(client, author, v, fmt="xlsx").json()["id"] for k, v in variants.items()}
    healthy = _bulk(client, author, _csv(uuid.uuid4().hex[:8], chapter, refs, 6)).json()["id"]  # queued after them
    _drain_until_idle()
    for kind, batch_id in bad.items():
        b = _batch(client, author, batch_id)
        assert b["status"] == "failed", (kind, b)
        assert "damaged, encrypted or compressed in a way that can't be read" in b["failure"], (kind, b["failure"])
        assert _row(batch_id).file_key is None
    assert _batch(client, author, healthy)["status"] == "previewed"  # the bad ones didn't stop the drain


def test_a_damaged_media_pack_manifest_is_refused(client: TestClient) -> None:
    with get_sessionmaker()() as db:
        author = Staff(client, db, ["content_author"], {"grades": [11], "subjects": ["biology"]})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("manifest.json", json.dumps({"schema_version": 1, "kind": "media", "grade": 11, "items": []}))
    for damaged in (
        _patch_member(buf.getvalue(), "manifest.json", flip_byte=True),
        _patch_member(buf.getvalue(), "manifest.json", flags=0x1),
        _patch_member(buf.getvalue(), "manifest.json", method=99),
    ):
        r = client.post(
            "/v1/studio/assets/manifest",
            headers={**author.headers, "Content-Type": "application/octet-stream"},
            content=damaged,
        )
        assert r.status_code == 422 and r.json()["code_reason"] == "MEDIA_PACK", r.text
        assert "damaged, encrypted or compressed" in r.json()["detail"]


def test_unexpected_errors_are_retried_after_a_pause_then_failed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    author = _author(client)
    chapter, refs = _setup()
    flaky_run = uuid.uuid4().hex[:8]
    flaky = _bulk(client, author, _csv(flaky_run, chapter, refs, 6)).json()["id"]
    healthy = _bulk(client, author, _csv(uuid.uuid4().hex[:8], chapter, refs, 6)).json()["id"]
    real = imports._validate_row

    def database_trouble(db: Any, who: Any, kind: str, raw: dict[str, Any], cache: dict[Any, bool]) -> Any:
        if str(raw.get("external_id", "")).startswith(f"BULK-{flaky_run}-"):
            raise ConnectionError("fixture: the database connection dropped")
        return real(db, who, kind, raw, cache)

    monkeypatch.setattr(imports, "_validate_row", database_trouble)

    _drain_until_idle()
    b = _row(flaky)
    assert b.status == "validating" and b.failure is None and b.attempts == 1  # not blamed on the author's file
    assert b.lease_owner is None and b.last_error and "ConnectionError" in b.last_error
    assert _batch(client, author, healthy)["status"] == "previewed"  # the queue went on
    _drain_until_idle()
    assert _row(flaky).attempts == 1  # it waits out its pause rather than looping

    for _ in range(bulk_imports.MAX_ATTEMPTS - 1):
        _expire(flaky)
        _drain_until_idle()
    failed = _batch(client, author, flaky)
    assert failed["status"] == "failed" and f"after {bulk_imports.MAX_ATTEMPTS} tries" in failed["failure"]
    assert "problem on our side" in failed["failure"] and _row(flaky).file_key is None


def test_a_batch_that_keeps_killing_its_worker_is_failed_not_retried_forever(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    b = _bulk(client, author, _csv(uuid.uuid4().hex[:8], chapter, refs, 6)).json()["id"]
    with get_sessionmaker()() as db:  # five workers died holding it: their claims were counted, nothing recorded
        db.execute(
            text(
                "update content_import_batch set status = 'validating', attempts = :n, lease_owner = 'dead#1', "
                "lease_expires_at = now() - interval '1 second' where id = :i"
            ),
            {"n": bulk_imports.MAX_ATTEMPTS, "i": b},
        )
        db.commit()
    _drain_until_idle()
    assert _batch(client, author, b)["status"] == "failed"


# ------------------------------------------------------------------ OCT14-05
def _suspend(client: TestClient, user_id: uuid.UUID) -> Staff:
    with get_sessionmaker()() as db:
        admin = Staff(client, db, ["owner_admin"], mfa=True)
    r = client.post(
        f"/v1/admin/users/{user_id}/suspend", headers=admin.headers, json={"reason": "Fixture: incident drill"}
    )
    assert r.status_code == 200, r.text
    return admin


def test_a_suspended_authors_queued_commit_writes_nothing(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]
    data = _csv(run, chapter, refs, 6)
    b = _bulk(client, author, data).json()["id"]
    _drain_until_idle()
    assert client.post(f"/v1/studio/imports/{b}/commit", headers=author.headers).json()["status"] == "committing"
    admin = _suspend(client, author.id)
    _drain_until_idle()
    failed = _row(b)
    assert failed.status == "failed" and "no longer active" in (failed.failure or "")
    assert _items(f"BULK-{run}-") == 0

    back = client.post(f"/v1/admin/users/{author.id}/reinstate", headers=admin.headers, json={"reason": "Fixture"})
    assert back.status_code == 200
    _drain_until_idle()
    assert _row(b).status == "failed"  # reinstating doesn't revive it: the author uploads again
    again = _bulk(client, author, data).json()["id"]
    _drain_until_idle()
    assert client.post(f"/v1/studio/imports/{again}/commit", headers=author.headers).json()["status"] == "committing"
    _drain_until_idle()
    assert _row(again).status == "committed" and _items(f"BULK-{run}-") == 6  # active and authorised: it writes


def test_a_suspended_authors_queued_file_is_not_checked(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    b = _bulk(client, author, _csv(uuid.uuid4().hex[:8], chapter, refs, 6)).json()["id"]
    _suspend(client, author.id)
    _drain_until_idle()
    failed = _row(b)
    assert failed.status == "failed" and "no longer active" in (failed.failure or "") and not failed.rows_checked


def test_a_revoked_role_stops_a_queued_commit(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]
    b = _bulk(client, author, _csv(run, chapter, refs, 6)).json()["id"]
    _drain_until_idle()
    assert client.post(f"/v1/studio/imports/{b}/commit", headers=author.headers).json()["status"] == "committing"
    with get_sessionmaker()() as db:
        db.execute(
            text("update staff_role_grant set revoked_at = now() where user_id = :u and revoked_at is null"),
            {"u": str(author.id)},
        )
        db.commit()
    _drain_until_idle()
    failed = _row(b)
    assert failed.status == "failed" and "can no longer be imported" in (failed.failure or ""), failed.failure
    assert _items(f"BULK-{run}-") == 0
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count(ContentItem.id)).where(ContentItem.created_by == author.id)) == 0


# ------------------------------------------------------------------ deployment: orphaned uploads
def test_reconcile_removes_only_old_uploads_that_no_batch_names(client: TestClient) -> None:
    import os
    import time

    author = _author(client)
    chapter, refs = _setup()
    named = _bulk(client, author, _csv(uuid.uuid4().hex[:8], chapter, refs, 6)).json()["id"]
    named_key = _row(named).file_key
    assert named_key
    root = bulk_imports._root()
    old_orphan, fresh_orphan = root / f"{uuid.uuid4()}.upload", root / f"{uuid.uuid4()}.upload"
    old_orphan.write_bytes(b"orphan")
    fresh_orphan.write_bytes(b"still streaming")
    two_hours_ago = time.time() - 7200
    for path in (old_orphan, root / named_key):
        os.utime(path, (two_hours_ago, two_hours_ago))
    with get_sessionmaker()() as db:
        listed = bulk_imports.reconcile(db, apply=False)
        assert old_orphan.name in listed and fresh_orphan.name not in listed and named_key not in listed
        assert old_orphan.exists()  # listing deletes nothing
        bulk_imports.reconcile(db, apply=True)
    assert not old_orphan.exists() and fresh_orphan.exists() and (root / named_key).exists()
    fresh_orphan.unlink()
