"""P06.S4.T3 (WORKFLOW-REHEARSAL-01): the complete staff content workflow, end to end, with labelled technical
fixtures (the owner's real material waits on content approval). Import a batch alongside malformed copies, correct
it, survive an interrupted commit, prove a repeat import changes nothing, publish only reviewed and corrected records,
see an incompatible block refused, then revise and roll a release back."""

from __future__ import annotations

import copy
import sys
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as OrmSession

from portal_api.db import get_sessionmaker
from portal_api.modules.content.models import ContentItem
from tests.test_content_import import _doc, _preview
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs, _save
from tests.test_mcq_items import CHECKS, VALID

SCOPE = {"grades": [11], "subjects": ["biology"]}


def _row(ext: str, chapter: str, refs: list[dict[str, Any]], stem: str, extra_blocks: list[Any] | None = None) -> Any:
    body = copy.deepcopy(VALID)
    body["stem"] = [{"type": "paragraph", "text": stem}, *(extra_blocks or [])]
    return {"external_id": ext, "chapter": chapter, "title": f"Fixture {ext}", "body": body, "source_refs": refs}


def _live(client: TestClient, who: Staff, item_id: str) -> int:
    """The version learners see (the detail lists `published` separately only when it differs from the working one)."""
    d = client.get(f"/v1/studio/items/{item_id}", headers=who.headers).json()
    assert d["availability"] == "live"
    return int((d["published"] or d["working"])["number"])


@pytest.fixture
def interrupt(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Fail the next commit made inside the import commit step, as a dropped database connection would."""
    state = {"fail_next": 0}
    original = OrmSession.commit

    def inside_import_commit() -> bool:
        f = sys._getframe(2)
        while f is not None:
            if f.f_code.co_name == "commit" and f.f_globals.get("__name__") == "portal_api.modules.content.imports":
                return True
            f = f.f_back  # type: ignore[assignment]
        return False

    def commit(self: OrmSession) -> None:
        if state["fail_next"] > 0 and inside_import_commit():
            state["fail_next"] -= 1
            raise OperationalError("COMMIT", {}, Exception("injected interruption"))
        original(self)

    monkeypatch.setattr(OrmSession, "commit", commit)
    return state


def test_the_staff_workflow_from_import_to_rollback(client: TestClient, interrupt: dict[str, int]) -> None:
    with get_sessionmaker()() as db:
        author = Staff(client, db, ["content_author"], SCOPE)
        reviewer = Staff(client, db, ["subject_reviewer"], SCOPE)
        publisher = Staff(client, db, ["publisher"], SCOPE, mfa=True)
        chapter, doc = _chapter(db, 11, "biology", 3)
        _confirm_rights(client, db, doc)
        key, refs = chapter.natural_key, _refs(chapter, doc)
    run = uuid.uuid4().hex[:8]
    eq = {"type": "equation", "latex": "x^2", "text_alt": "x squared"}  # needs a fallback the row doesn't have
    good = [_row(f"WF-{run}-{n}", key, refs, f"Fixture rehearsal stem {n} {run}") for n in (1, 2, 3)]
    unrenderable = _row(f"WF-{run}-4", key, refs, f"Fixture rehearsal stem 4 {run}", [eq])

    # 1. Malformed copies are caught in the preview; nothing is written.
    broken = copy.deepcopy(good[0])
    broken["body"]["correct_option_id"] = "o9"
    wrong_chapter = {**copy.deepcopy(good[1]), "chapter": "no-such-chapter"}
    bad = _preview(client, author, _doc(*good, broken, wrong_chapter)).json()
    assert bad["counts"]["error"] == 2
    assert client.post(f"/v1/studio/imports/{bad['id']}/commit", headers=author.headers).status_code == 409

    # 2. The corrected file; its commit is interrupted, nothing half-written, and a retry completes it.
    clean = _preview(client, author, _doc(*good, unrenderable)).json()
    assert clean["counts"] == {"create": 4}, clean
    interrupt["fail_next"] = 1
    cut = client.post(f"/v1/studio/imports/{clean['id']}/commit", headers=author.headers)
    assert cut.status_code == 503, cut.text
    with get_sessionmaker()() as db:
        assert db.scalar(select(ContentItem).where(ContentItem.external_ref == f"WF-{run}-1")) is None
    assert client.get(f"/v1/studio/imports/{clean['id']}", headers=author.headers).json()["status"] == "previewed"
    done = client.post(f"/v1/studio/imports/{clean['id']}/commit", headers=author.headers)
    assert done.status_code == 200 and done.json()["counts"]["written_created"] == 4, done.text
    ids = {row["external_id"]: row["item_id"] for row in done.json()["rows"]}

    # 3. Importing the same file again changes nothing.
    again = _preview(client, author, _doc(*good, unrenderable)).json()
    assert again["counts"] == {"unchanged": 4}

    # 4. Review and publish: corrected records go live, the unrenderable one is refused.
    review = {"decision": "approve", "comment": "Fixture rehearsal check", "checklist": CHECKS}
    for ext, item_id in ids.items():
        assert _post(client, author, item_id, "submit").status_code == 200
        assert _post(client, reviewer, item_id, "review", review).status_code == 200
        published = _post(client, publisher, item_id, "publish")
        if ext.endswith("-4"):
            assert published.status_code == 422 and any("fallback" in e for e in published.json()["errors"])
        else:
            assert published.status_code == 200, published.text

    # 5. Revise a live question, publish version 2, then roll the release back to version 1.
    first = ids[f"WF-{run}-1"]
    assert _post(client, author, first, "revise", {"reason": "Fixture: clearer wording"}).status_code == 200
    current = client.get(f"/v1/studio/items/{first}", headers=author.headers).json()
    v2 = copy.deepcopy(current["working"]["body"])
    v2["stem"] = [{"type": "paragraph", "text": f"Fixture rehearsal stem 1, reworded {run}"}]
    assert _save(client, author, current, body=v2, refs=refs).status_code == 200
    assert _post(client, author, first, "submit").status_code == 200
    assert _post(client, reviewer, first, "review", review).status_code == 200
    assert _post(client, publisher, first, "publish").status_code == 200
    assert _live(client, author, first) == 2
    back = _post(client, publisher, first, "rollback", {"reason": "Fixture: version 2 confused learners"})
    assert back.status_code == 200, back.text
    assert _live(client, author, first) == 1
