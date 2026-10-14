"""P06.S2.T1 (IMPORT-BULK-01): large imports checked and committed by the import worker.

* A file over the request limits is queued (202), streamed to private storage, and checked by the worker in chunks
  with the preview's own rules; it then is an ordinary preview, and its upload is deleted.
* A worker that dies part-way is resumed by another after its lease runs out: no row is checked twice or skipped.
* Committing a large preview is queued too; the worker writes every row in one transaction, or none.
* Broken files fail with a reason and leave nothing behind; a queued batch can be discarded; only its author sees it.

The limits are lowered for the tests, so a handful of fixture rows stands for thousands. Rows are technical fixtures,
not academic content.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from portal_api.db import get_sessionmaker
from portal_api.modules.content import bulk_imports, imports
from portal_api.modules.content.models import ContentImportBatch, ContentImportRow, ContentItem
from tests.test_content_import import SCOPE, _author, _preview, _setup
from tests.test_content_workflow import Staff

HEADER = "external_id,chapter,title,stem,option_a,option_b,option_c,option_d,correct,source_document_id,pdf_from,pdf_to"


@pytest.fixture(autouse=True)
def _small_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(imports, "MAX_ROWS", 5)  # a request preview takes at most 5 rows here
    monkeypatch.setattr(bulk_imports, "CHUNK", 3)
    monkeypatch.setattr(bulk_imports, "SYNC_COMMIT_ROWS", 4)


def _csv(run: str, chapter: str, refs: list[dict[str, Any]], n: int) -> bytes:
    r = refs[0]
    lines = [
        f"BULK-{run}-{i},{chapter},Fixture bulk {i},Fixture bulk stem {run} {i},Fixture A,Fixture B,Fixture C,"
        f"Fixture D,B,{r['source_document_id']},{r['pdf_from']},{r['pdf_to']}"
        for i in range(1, n + 1)
    ]
    return ("\n".join([HEADER, *lines]) + "\n").encode()


def _bulk(client: TestClient, who: Staff, data: bytes, fmt: str = "csv") -> Any:
    return client.post(
        f"/v1/studio/imports/bulk?format={fmt}&filename=fixture-bulk.{fmt}",
        headers={**who.headers, "Content-Type": "application/octet-stream"},
        content=data,
    )


def _batch(client: TestClient, who: Staff, batch_id: str) -> dict[str, Any]:
    r = client.get(f"/v1/studio/imports/{batch_id}", headers=who.headers)
    assert r.status_code == 200, r.text
    return dict(r.json())


def _drain(owner: str = "test-worker") -> None:
    with get_sessionmaker()() as db:
        bulk_imports.work(db, owner)


def _file_key(batch_id: str) -> str | None:
    with get_sessionmaker()() as db:
        b = db.get(ContentImportBatch, uuid.UUID(batch_id))
        assert b is not None
        return b.file_key


def _items(prefix: str) -> int:
    with get_sessionmaker()() as db:
        return int(
            db.scalar(select(func.count(ContentItem.id)).where(ContentItem.external_ref.like(f"{prefix}%"))) or 0
        )


def test_a_large_file_is_checked_and_committed_by_the_worker(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]
    data = _csv(run, chapter, refs, 8)
    assert _preview(client, author, data, fmt="csv").status_code == 413  # too many rows for a request preview

    queued = _bulk(client, author, data)
    assert queued.status_code == 202, queued.text
    b = queued.json()
    assert b["status"] == "queued" and b["kind"] == "pending" and b["rows"] == []
    key = _file_key(b["id"])
    assert key and (bulk_imports._root() / key).exists()

    _drain()
    ready = _batch(client, author, b["id"])
    assert ready["status"] == "previewed" and ready["kind"] == "mcq", ready
    assert ready["counts"] == {"create": 8} and (ready["rows_total"], ready["rows_checked"]) == (8, 8)
    assert [r["row"] for r in ready["rows"]] == list(range(1, 9))
    assert _file_key(b["id"]) is None and not (bulk_imports._root() / key).exists()  # the upload is gone
    report = client.get(f"/v1/studio/imports/{b['id']}/report.csv", headers=author.headers)
    assert report.status_code == 200 and report.text.count("\n") >= 9  # the correction report works as for any preview

    committing = client.post(f"/v1/studio/imports/{b['id']}/commit", headers=author.headers)
    assert committing.status_code == 200 and committing.json()["status"] == "committing"  # 8 rows > 4: the worker
    assert _items(f"BULK-{run}-") == 0
    _drain()
    done = _batch(client, author, b["id"])
    assert done["status"] == "committed" and done["counts"]["written_created"] == 8
    assert _items(f"BULK-{run}-") == 8

    again = _bulk(client, author, data).json()
    _drain()
    assert _batch(client, author, again["id"])["counts"] == {"unchanged": 8}  # idempotent, as a preview is


def test_a_worker_that_dies_part_way_is_resumed_without_repeating_rows(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    author = _author(client)
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]
    b = _bulk(client, author, _csv(run, chapter, refs, 8)).json()

    real, calls = imports._validate_row, []

    def dies_on_row_five(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(1)
        if len(calls) == 5:  # the first chunk (rows 1-3) is stored; the worker dies inside the second
            raise RuntimeError("fixture: the worker process died")
        return real(*args, **kwargs)

    monkeypatch.setattr(imports, "_validate_row", dies_on_row_five)
    with pytest.raises(RuntimeError), get_sessionmaker()() as db:
        bulk_imports.work(db, "worker-that-dies")
    monkeypatch.setattr(imports, "_validate_row", real)
    stuck = _batch(client, author, b["id"])
    assert stuck["status"] == "validating" and stuck["rows_checked"] == 3
    assert stuck["rows"] == []  # a poll gets progress, not the rows stored so far

    _drain("second-worker")  # the lease is still held: nothing happens yet
    assert _batch(client, author, b["id"])["status"] == "validating"
    with get_sessionmaker()() as db:
        db.execute(
            text("update content_import_batch set lease_expires_at = now() - interval '1 minute' where id = :i"),
            {"i": b["id"]},
        )
        db.commit()
    _drain("second-worker")
    done = _batch(client, author, b["id"])
    assert done["status"] == "previewed" and done["counts"] == {"create": 8}
    with get_sessionmaker()() as db:
        numbers = list(
            db.scalars(
                select(ContentImportRow.row_number)
                .where(ContentImportRow.batch_id == uuid.UUID(b["id"]))
                .order_by(ContentImportRow.row_number)
            )
        )
    assert numbers == list(range(1, 9))  # every row exactly once


def test_a_bulk_commit_writes_every_row_or_none(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]
    data = _csv(run, chapter, refs, 6)
    b = _bulk(client, author, data).json()
    _drain()
    assert _batch(client, author, b["id"])["counts"] == {"create": 6}

    # Meanwhile, row 3 is imported on its own: the bulk preview is now out of date for that row.
    one = data.decode().splitlines()
    single = _preview(client, author, ("\n".join([one[0], one[3]]) + "\n").encode(), fmt="csv").json()
    assert client.post(f"/v1/studio/imports/{single['id']}/commit", headers=author.headers).status_code == 200
    assert _items(f"BULK-{run}-") == 1

    assert client.post(f"/v1/studio/imports/{b['id']}/commit", headers=author.headers).json()["status"] == "committing"
    _drain()
    failed = _batch(client, author, b["id"])
    assert failed["status"] == "failed" and "Row 3" in failed["failure"] and "Nothing was imported" in failed["failure"]
    assert _items(f"BULK-{run}-") == 1  # none of the other five rows was written


def test_broken_or_discarded_bulk_files_leave_nothing_behind(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    author = _author(client)
    bad = _bulk(client, author, b'{"schema_version": 1, "kind": "mcq", "items": [', fmt="json").json()
    bad_key = _file_key(bad["id"])
    _drain()
    failed = _batch(client, author, bad["id"])
    assert failed["status"] == "failed" and "JSON" in failed["failure"]
    assert bad_key and not (bulk_imports._root() / bad_key).exists()
    assert client.post(f"/v1/studio/imports/{bad['id']}/commit", headers=author.headers).status_code == 409

    queued = _bulk(client, author, b"external_id,chapter\n", fmt="csv").json()
    key = _file_key(queued["id"])
    gone = client.post(f"/v1/studio/imports/{queued['id']}/discard", headers=author.headers)
    assert gone.status_code == 200 and gone.json()["status"] == "discarded"
    assert key and not (bulk_imports._root() / key).exists()
    _drain()
    assert _batch(client, author, queued["id"])["status"] == "discarded"  # the worker leaves it alone

    monkeypatch.setattr(bulk_imports, "BULK", imports.Limits(max_bytes=100, max_rows=10, max_part=100))
    before = {p.name for p in bulk_imports._root().iterdir()}
    assert _bulk(client, author, b"x" * 200).status_code == 413
    assert {p.name for p in bulk_imports._root().iterdir()} == before  # the partial upload was removed
    assert _bulk(client, author, b"").status_code == 422

    with get_sessionmaker()() as db:
        reviewer = Staff(client, db, ["subject_reviewer"], SCOPE)
        other = Staff(client, db, ["content_author"], SCOPE)
    assert _bulk(client, reviewer, b"external_id\n").status_code == 403
    assert client.get(f"/v1/studio/imports/{bad['id']}", headers=other.headers).status_code == 404
    assert client.post("/v1/studio/imports/bulk", content=b"x").status_code == 401
