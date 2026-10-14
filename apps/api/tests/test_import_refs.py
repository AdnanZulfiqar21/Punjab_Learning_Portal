"""P06.S2.T1 / P08.S3.T2 (IMPORT-REFS-01): imports that reference other items.

* A rubric row names its written question (external_id or ID). It is created attached to that question, marking the
  question's current version; a question already having another rubric, or a question in another chapter, is an error.
* A question row may name a variant family (an existing question in the same chapter) and a passage.
* Passages import like lessons. Every row is still only a draft that goes through review.

Rows are technical fixtures, not academic content.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.content.models import ContentItem, ContentVersion
from tests.test_content_import import _author, _preview, _row, _setup
from tests.test_written_records import QUESTION, _rubric


def _doc(kind: str, *rows: dict[str, Any]) -> bytes:
    return json.dumps({"schema_version": 1, "kind": kind, "items": list(rows)}).encode()


def _import(client: TestClient, who: Any, kind: str, *rows: dict[str, Any]) -> dict[str, Any]:
    r = _preview(client, who, _doc(kind, *rows))
    assert r.status_code == 201, r.text
    batch = r.json()
    errors = [row for row in batch["rows"] if row["action"] == "error"]
    if errors:
        return {"errors": errors, "batch": batch}
    done = client.post(f"/v1/studio/imports/{batch['id']}/commit", headers=who.headers)
    assert done.status_code == 200, done.text
    return {"errors": [], "batch": done.json()}


def _item(kind: str, ext: str) -> ContentItem:
    with get_sessionmaker()() as db:
        item = db.scalar(select(ContentItem).where(ContentItem.kind == kind, ContentItem.external_ref == ext))
        assert item is not None
        db.expunge(item)
        return item


def test_a_rubric_is_imported_onto_its_question(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]
    question = {
        "external_id": f"WQ-{run}",
        "chapter": chapter,
        "title": "Fixture written",
        "body": QUESTION,
        "source_refs": refs,
    }
    assert _import(client, author, "written", question)["errors"] == []
    q = _item("written", f"WQ-{run}")

    body = _rubric(str(uuid.uuid4()))  # whatever version it names, the import marks the question's current version
    rubric = {
        "external_id": f"WR-{run}",
        "chapter": chapter,
        "title": "Fixture rubric",
        "question": f"WQ-{run}",
        "body": body,
        "source_refs": refs,
    }
    assert _import(client, author, "rubric", rubric)["errors"] == []
    r = _item("rubric", f"WR-{run}")
    assert r.parent_item_id == q.id and r.state == "draft"
    with get_sessionmaker()() as db:
        version = db.get(ContentVersion, r.working_version_id)
        assert version is not None and version.body["question_version_id"] == str(q.working_version_id)

    again = _preview(client, author, _doc("rubric", rubric)).json()
    assert again["counts"] == {"unchanged": 1}  # idempotent
    second = {**rubric, "external_id": f"WR2-{run}"}
    refused = _import(client, author, "rubric", second)["errors"]
    assert refused and any("already has a rubric" in e for e in refused[0]["errors"])
    missing = _import(client, author, "rubric", {**rubric, "external_id": f"WR3-{run}", "question": "no-such-question"})
    assert any("question:" in e for e in missing["errors"][0]["errors"])


def test_variants_and_passages_are_linked_on_import(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]
    base = _row(f"VB-{run}", chapter, refs, f"Fixture base stem {run}")
    assert _import(client, author, "mcq", base)["errors"] == []
    variant = {**_row(f"VV-{run}", chapter, refs, f"Fixture variant stem {run}"), "family": f"VB-{run}"}
    assert _import(client, author, "mcq", variant)["errors"] == []
    b, v = _item("mcq", f"VB-{run}"), _item("mcq", f"VV-{run}")
    assert v.family_id == b.family_id and v.id != b.id

    passage = {
        "external_id": f"PS-{run}",
        "chapter": chapter,
        "title": "Fixture passage",
        "body": {"blocks": [{"type": "paragraph", "text": f"Fixture passage text {run}."}]},
        "source_refs": refs,
    }
    assert _import(client, author, "passage", passage)["errors"] == []
    p = _item("passage", f"PS-{run}")
    linked = {**_row(f"VP-{run}", chapter, refs, f"Fixture passage stem {run}"), "passage": f"PS-{run}"}
    assert _import(client, author, "mcq", linked)["errors"] == []
    with get_sessionmaker()() as db:
        item = db.scalar(select(ContentItem).where(ContentItem.external_ref == f"VP-{run}"))
        assert item is not None
        version = db.get(ContentVersion, item.working_version_id)
        assert version is not None and version.body["passage_id"] == str(p.id)

    wrong = {**_row(f"VX-{run}", chapter, refs, f"Fixture stem {run}"), "family": "no-such-question"}
    assert any("family:" in e for e in _import(client, author, "mcq", wrong)["errors"][0]["errors"])
