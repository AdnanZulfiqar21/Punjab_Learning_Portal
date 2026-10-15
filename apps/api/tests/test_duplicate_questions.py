"""P08.S3.T1 (DUP-STEMS-01): a question that duplicates, or nearly duplicates, another question of its class and subject
is flagged for the academic reviewer; a variant of the same family and a different question are not. Technical
fixture questions with unique stems, so other tests' fixtures in the shared database don't match."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from portal_api.modules.content import duplicates
from tests.test_content_workflow import Staff, _chapter, _post, _refs
from tests.test_mcq_items import VALID, _new_mcq, _p, _save


def _body(stem: str, option_one: str = "Fixture option one") -> dict[str, Any]:
    body = copy.deepcopy(VALID)
    body["stem"] = _p(stem)
    body["options"][0]["blocks"] = _p(option_one)
    return body


def test_duplicates_are_flagged_for_review_and_variants_are_not(client: TestClient, db: Session) -> None:
    scope = {"grades": [11], "subjects": ["biology"]}
    author = Staff(client, db, ["content_author"], scope)
    reviewer = Staff(client, db, ["subject_reviewer"], scope)
    chapter, doc = _chapter(db, 11, "biology", 1)
    tag = uuid.uuid4().hex[:10]
    stem = f"Fixture {tag}: which of these structures stores genetic information in the cell nucleus of a plant?"

    def submitted(body: dict[str, Any], **extra: Any) -> dict[str, Any]:
        item = _new_mcq(client, author, str(chapter.id), **extra)
        saved = _save(client, author, item, body, _refs(chapter, doc))
        assert saved.status_code == 200, saved.text
        sub = _post(client, author, item["id"], "submit")
        assert sub.status_code == 200, sub.text
        return dict(sub.json())

    def flags(item: dict[str, Any]) -> list[str]:
        r = client.get(f"/v1/studio/items/{item['id']}", headers=reviewer.headers)
        assert r.status_code == 200, r.text
        return list(r.json()["duplicate_warnings"])

    first = submitted(_body(stem))
    assert flags(first) == []
    same = submitted(_body(stem))
    [exact] = flags(same)
    assert "exactly" in exact and first["id"][:8] in exact
    near = submitted(_body(stem.replace("stores", "keeps")))
    near_flags = flags(near)
    assert len(near_flags) == 2 and all("nearly identical" in f for f in near_flags)
    other = submitted(_body(f"Fixture {tag}: name the organelle where photosynthesis happens in a leaf cell."))
    assert flags(other) == []
    variant = submitted(_body(stem), family_of=first["id"])
    assert all(first["id"][:8] not in f for f in flags(variant))  # a variant of the same family is meant to be alike


def test_signatures_fold_case_spacing_and_option_order() -> None:
    a = _body("Fixture: Which ONE is right?")
    b = copy.deepcopy(_body("fixture   which one is right"))
    b["options"].reverse()
    assert duplicates.signature("mcq", a) == duplicates.signature("mcq", b)
    assert duplicates.signature("mcq", {"stem": []}) == ""
    assert duplicates.signature("lesson", a).startswith("fixture which one is right")
    assert not duplicates._alike("short text", "a much much longer and different text altogether")
