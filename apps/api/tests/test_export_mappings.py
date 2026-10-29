"""P06.S4.T2 (EXPORT-02): the portable content export (schema version 2) carries the concept mappings, prerequisites
and syllabus inclusion records of the book it exports, and a reference for every archived asset version its items name.
Class 11 and 12 are never mixed. Technical fixture concepts, records, images and lessons only."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.modules.curriculum.models import Topic
from tests import test_content_workflow
from tests.test_assets import SRC, _asset, _upload
from tests.test_concepts import BIO_BOTH, _concept, _topics
from tests.test_concepts import URL as CONCEPTS
from tests.test_content_workflow import Staff, _chapter, _create, _refs, _save
from tests.test_inclusion import _record
from tests.test_written_attempts import _png

team = test_content_workflow.team  # the Class 11 Biology staff fixture


def _key(db: Session, topic_id: str) -> str:
    return str(db.scalar(select(Topic.natural_key).where(Topic.id == topic_id)))


def test_the_export_carries_concepts_inclusion_and_asset_references(
    client: TestClient, db: Session, team: dict[str, Staff]
) -> None:
    author = Staff(client, db, ["content_author"], BIO_BOTH)
    reviewer = Staff(client, db, ["subject_reviewer"], BIO_BOTH)
    xi, xii = _topics(db, 11)[0], _topics(db, 12)[0]
    base = _concept(client, author)  # taught in both books
    assert (
        client.put(f"{CONCEPTS}/{base['id']}/topics", headers=author.headers, json={"topic_ids": [xi, xii]}).status_code
        == 200
    )
    chapter, doc = _chapter(db, 11, "biology")
    refs = [{"source_document_id": str(doc.id), "pdf_from": chapter.pdf_start, "pdf_to": chapter.pdf_start}]
    assert client.put(f"{CONCEPTS}/{base['id']}", headers=author.headers, json={"source_refs": refs}).status_code == 200
    assert client.post(f"{CONCEPTS}/{base['id']}/publish", headers=reviewer.headers).status_code == 200
    later = _concept(client, author)
    assert (
        client.put(f"{CONCEPTS}/{later['id']}/topics", headers=author.headers, json={"topic_ids": [xi]}).status_code
        == 200
    )
    assert (
        client.post(
            f"{CONCEPTS}/{later['id']}/prerequisites", headers=author.headers, json={"requires_id": base["id"]}
        ).status_code
        == 200
    )
    only_xii = _concept(client, author)
    assert (
        client.put(f"{CONCEPTS}/{only_xii['id']}/topics", headers=author.headers, json={"topic_ids": [xii]}).status_code
        == 200
    )
    assert _record(client, author, base).status_code == 201

    image = _asset(client, team["author"], "image", "Fixture export diagram")
    version = _upload(client, team["author"], image["id"], _png(seed=881))
    assert version.status_code == 201, version.text
    vid = version.json()["id"]
    item = _create(client, team["author"], chapter, title="Fixture lesson with a diagram")
    body = {
        "blocks": [
            {"type": "paragraph", "text": "Technical fixture paragraph."},
            {"type": "diagram", "asset_version_id": vid, "alt": "Fixture diagram", "caption": "Fixture caption"},
        ]
    }
    assert _save(client, team["author"], item, body=body, refs=_refs(chapter, doc)).status_code == 200

    r = client.get("/v1/studio/export?grade=11&subject=biology", headers=team["publisher"].headers)
    assert r.status_code == 200, r.text
    out = json.loads(r.content)
    assert out["schema_version"] == 2
    concepts = {c["code"]: c for c in out["concepts"]}
    assert base["code"] in concepts and later["code"] in concepts
    assert only_xii["code"] not in concepts  # mapped only to the Class 12 book
    assert concepts[base["code"]]["topics"] == [_key(db, xi)]  # its Class 12 topic stays out of a Class 11 file
    assert concepts[later["code"]]["requires"] == [{"code": base["code"], "bridging_lesson_id": None}]
    [rec] = concepts[base["code"]]["inclusion"]
    assert (rec["scope"], rec["year"], rec["state"], rec["status"]) == ("mdcat", 2026, "included", "draft")
    [ref] = [a for a in out["assets"] if a["asset_version_id"] == vid]
    assert ref["missing"] is False and ref["kind"] == "image" and ref["asset_id"] == image["id"]
    assert len(ref["sha256"]) == 64 and ref["bytes"] > 0 and ref["provenance"]["source"] == SRC["source"]
    assert "@example.com" not in r.text  # still no staff identities
