"""P06.S2 (IMPORT-01): structured import with a dry-run preview, row-level errors, a correction report and an atomic,
idempotent commit that only ever creates or updates drafts. Rows are technical fixtures, not academic content."""

from __future__ import annotations

import copy
import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.content.models import ContentItem
from tests.test_content_workflow import Staff, _chapter, _refs
from tests.test_mcq_items import VALID

SCOPE = {"grades": [11], "subjects": ["chemistry"]}


def _author(client: TestClient, scope: dict[str, Any] | None = None) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, ["content_author"], scope or SCOPE)


def _setup() -> tuple[str, list[dict[str, Any]]]:
    with get_sessionmaker()() as db:
        chapter, doc = _chapter(db, 11, "chemistry")
        return chapter.natural_key, _refs(chapter, doc)


def _row(ext: str, chapter: str, refs: list[dict[str, Any]], stem: str, key: str = "o2") -> dict[str, Any]:
    body = copy.deepcopy(VALID)
    body["stem"] = [{"type": "paragraph", "text": stem}]
    body["correct_option_id"] = key
    return {"external_id": ext, "chapter": chapter, "title": f"Fixture {ext}", "body": body, "source_refs": refs}


def _doc(*rows: dict[str, Any]) -> bytes:
    return json.dumps({"schema_version": 1, "kind": "mcq", "items": list(rows)}).encode()


def _preview(client: TestClient, who: Staff, data: bytes, fmt: str = "json") -> Any:
    return client.post(
        f"/v1/studio/imports?format={fmt}&filename=fixture.{fmt}",
        headers={**who.headers, "Content-Type": "application/octet-stream"},
        content=data,
    )


def test_preview_reports_rows_and_commit_creates_drafts_once(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]
    good = [
        _row(f"FX-{run}-1", chapter, refs, f"Fixture stem one {run}"),
        _row(f"FX-{run}-2", chapter, refs, f"Fixture stem two {run}"),
    ]
    bad_body = _row(f"FX-{run}-3", chapter, refs, f"Fixture stem three {run}")
    bad_body["body"]["correct_option_id"] = "o9"
    bad_chapter = _row(f"FX-{run}-4", "no-such-chapter", refs, "Fixture stem four")
    dup = _row(f"FX-{run}-1", chapter, refs, "Fixture duplicate id")
    r = _preview(client, author, _doc(*good, bad_body, bad_chapter, dup))
    assert r.status_code == 201, r.text
    batch = r.json()
    assert batch["status"] == "previewed" and batch["counts"] == {"create": 2, "error": 3}
    errors = {row["row"]: row["errors"] for row in batch["rows"] if row["action"] == "error"}
    assert any("body:" in e for e in errors[3]) and any("chapter" in e for e in errors[4])
    assert any("Duplicate external_id" in e for e in errors[5])
    with get_sessionmaker()() as db:  # a preview writes no content
        assert db.scalar(select(ContentItem).where(ContentItem.external_ref == f"FX-{run}-1")) is None
    report = client.get(f"/v1/studio/imports/{batch['id']}/report.csv", headers=author.headers)
    assert report.status_code == 200 and report.headers["content-type"].startswith("text/csv")
    assert "Duplicate external_id" in report.text and report.text.splitlines()[0].startswith("row,external_id,action")
    assert client.post(f"/v1/studio/imports/{batch['id']}/commit", headers=author.headers).status_code == 409

    clean = _preview(client, author, _doc(*good)).json()
    done = client.post(f"/v1/studio/imports/{clean['id']}/commit", headers=author.headers)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "committed" and done.json()["counts"]["written_created"] == 2
    assert client.post(f"/v1/studio/imports/{clean['id']}/commit", headers=author.headers).status_code == 409
    item_ids = [row["item_id"] for row in done.json()["rows"]]
    for item_id in item_ids:
        item = client.get(f"/v1/studio/items/{item_id}", headers=author.headers).json()
        assert item["state"] == "draft" and item["availability"] == "unpublished"  # drafts only, never published

    # The same file again: every row unchanged, nothing written.
    again = _preview(client, author, _doc(*good)).json()
    assert again["counts"] == {"unchanged": 2}
    assert (
        client.post(f"/v1/studio/imports/{again['id']}/commit", headers=author.headers)
        .json()["counts"]
        .get("written_created", 0)
        == 0
    )
    # A changed row updates its draft in place (same item, next revision).
    changed = copy.deepcopy(good[0])
    changed["body"]["correct_option_id"] = "o3"
    upd = _preview(client, author, _doc(changed)).json()
    assert upd["counts"] == {"update": 1} and upd["rows"][0]["item_id"] == item_ids[0]
    assert client.post(f"/v1/studio/imports/{upd['id']}/commit", headers=author.headers).status_code == 200
    item = client.get(f"/v1/studio/items/{item_ids[0]}", headers=author.headers).json()
    assert item["working"]["body"]["correct_option_id"] == "o3"


def test_imports_respect_scope_and_skip_items_in_review(client: TestClient) -> None:
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]
    outsider = _author(client, {"grades": [12], "subjects": ["chemistry"]})
    r = _preview(client, outsider, _doc(_row(f"FX-{run}-s", chapter, refs, "Fixture scope")))
    assert r.json()["counts"] == {"error": 1} and "can't draft" in r.json()["rows"][0]["errors"][0]
    author = _author(client)
    committed = _preview(client, author, _doc(_row(f"FX-{run}-r", chapter, refs, f"Fixture review {run}"))).json()
    done = client.post(f"/v1/studio/imports/{committed['id']}/commit", headers=author.headers).json()
    item_id = done["rows"][0]["item_id"]
    assert client.post(f"/v1/studio/items/{item_id}/submit", headers=author.headers, json={}).status_code == 200
    changed = _row(f"FX-{run}-r", chapter, refs, f"Fixture review changed {run}")
    skip = _preview(client, author, _doc(changed)).json()
    assert skip["counts"] == {"skip": 1} and "revision" in skip["rows"][0]["warnings"][-1]
    # Another author can't read or commit someone else's batch.
    other = _author(client)
    assert client.get(f"/v1/studio/imports/{skip['id']}", headers=other.headers).status_code == 404
    assert client.post(f"/v1/studio/imports/{skip['id']}/commit", headers=other.headers).status_code == 404
    assert (
        client.post(
            "/v1/studio/imports?format=json", headers={**_author(client, None).headers}, content=b""
        ).status_code
        == 422
    )


def test_csv_template_and_file_checks(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]
    header = (
        "external_id,chapter,title,stem,option_a,option_b,option_c,option_d,correct,explanation,"
        "source_document_id,pdf_from,pdf_to"
    )
    line = (
        f"FX-{run}-c,{chapter},Fixture CSV,Fixture CSV stem {run},Fixture A,Fixture B,Fixture C,Fixture D,B,"
        f"Fixture reason,{refs[0]['source_document_id']},{refs[0]['pdf_from']},{refs[0]['pdf_to']}"
    )
    csv_bytes = ("﻿" + header + "\n" + line + "\n").encode()
    r = _preview(client, author, csv_bytes, fmt="csv")
    assert r.status_code == 201, r.text
    assert r.json()["counts"] == {"create": 1}, r.json()["rows"]
    assert _preview(client, author, b"external_id,chapter\nx,y\n", fmt="csv").json()["code_reason"] == "CSV_HEADER"
    assert _preview(client, author, "caf\xe9".encode("latin-1")).json()["code_reason"] == "ENCODING"
    assert (
        _preview(client, author, b'{"schema_version": 2, "kind": "mcq", "items": []}').json()["code_reason"]
        == "SCHEMA_VERSION"
    )
    assert _preview(client, author, b"{" + b" " * (5 * 1024 * 1024)).status_code == 413
    reviewer = None
    with get_sessionmaker()() as db:
        reviewer = Staff(client, db, ["subject_reviewer"], SCOPE)
    assert _preview(client, reviewer, _doc(_row("x", chapter, refs, "x"))).status_code == 403
