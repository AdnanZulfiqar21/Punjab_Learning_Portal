"""P06.S2.T3 (SOURCE-INTAKE-01): the owner stores the exact registered original of a source privately; staff in its
class and subject view single PDF pages as images rendered in an isolated worker, never the PDF. Anything but the
registered bytes is refused. A labelled technical fixture source and a generated fixture PDF only (the real textbooks'
checksums are registered, but their files never enter the repository)."""

from __future__ import annotations

import hashlib
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _pdf

PDF = _pdf(3)
PDF2 = PDF + b"% second technical fixture\n"  # different bytes, so a different stored original


def _fixture_source(sha: str, pages: int) -> str:
    from portal_api.modules.curriculum.models import SourceDocument

    sid = uuid.uuid4()
    with get_sessionmaker()() as s:
        s.add(
            SourceDocument(
                id=sid,
                source_id=f"FX-{sid.hex[:10]}",
                grade_number=11,
                subject_code="biology",
                title="[FIXTURE] Technical source",
                file_path="fixture/not-a-real-book.pdf",
                sha256=sha,
                bytes=len(PDF),
                pdf_pages=pages,
                completeness="complete",
                missing_pages=[],
                duplicate_pages=[],
                rights="Technical fixture",
                status="fixture",
                metadata_json={},
            )
        )
        s.commit()
    return str(sid)


def _upload(client: TestClient, who: Staff, sid: str, data: bytes):  # type: ignore[no-untyped-def]
    return client.post(
        f"/v1/studio/sources/{sid}/original",
        headers={**who.headers, "Content-Type": "application/pdf"},
        content=data,
    )


def test_only_the_registered_original_is_stored_by_the_owner(client: TestClient, db: Session) -> None:
    sid = _fixture_source(hashlib.sha256(PDF).hexdigest(), 3)
    owner = Staff(client, db, ["owner_admin"], mfa=True)
    author = Staff(client, db, ["content_author"], {"grades": [11], "subjects": ["biology"]})
    assert _upload(client, author, sid, PDF).status_code == 403  # only the owner
    assert _upload(client, Staff(client, db, ["owner_admin"]), sid, PDF).status_code == 403  # and with MFA
    wrong = _upload(client, owner, sid, PDF + b"%tampered")
    assert wrong.status_code == 422 and wrong.json()["code_reason"] == "NOT_THE_ORIGINAL"
    ok = _upload(client, owner, sid, PDF)
    assert ok.status_code == 200, ok.text
    assert ok.json()["stored"] is True and ok.json()["sha256"] == hashlib.sha256(PDF).hexdigest()
    again = _upload(client, owner, sid, PDF)
    assert again.status_code == 200 and again.json()["stored"] is False  # written once, never replaced
    listed = next(s for s in client.get("/v1/studio/sources", headers=author.headers).json() if s["id"] == sid)
    assert listed["original_stored"] is True
    owners_view = client.get("/v1/studio/sources", headers=owner.headers)  # the owner reads the registry too
    assert owners_view.status_code == 200 and any(s["id"] == sid for s in owners_view.json())
    assert client.get("/v1/studio/sources", headers=Staff(client, db, []).headers).status_code == 403


def test_staff_in_scope_view_pages_as_images(client: TestClient, db: Session) -> None:
    sid = _fixture_source(hashlib.sha256(PDF2).hexdigest(), 3)
    owner = Staff(client, db, ["owner_admin"], mfa=True)
    reviewer = Staff(client, db, ["subject_reviewer"], {"grades": [11], "subjects": ["biology"]})
    before = client.get(f"/v1/studio/sources/{sid}/pages/1", headers=reviewer.headers)
    assert before.status_code == 404  # nothing stored yet
    assert _upload(client, owner, sid, PDF2).status_code == 200
    page = client.get(f"/v1/studio/sources/{sid}/pages/2", headers=reviewer.headers)
    assert page.status_code == 200 and page.headers["content-type"] == "image/png"
    assert page.content[:8] == b"\x89PNG\r\n\x1a\n" and page.headers["cache-control"].startswith("private")
    assert client.get(f"/v1/studio/sources/{sid}/pages/4", headers=reviewer.headers).status_code == 404
    xii = Staff(client, db, ["subject_reviewer"], {"grades": [12], "subjects": ["biology"]})
    assert client.get(f"/v1/studio/sources/{sid}/pages/1", headers=xii.headers).status_code == 404  # other class
    learner = Staff(client, db, [])
    assert client.get(f"/v1/studio/sources/{sid}/pages/1", headers=learner.headers).status_code == 403
