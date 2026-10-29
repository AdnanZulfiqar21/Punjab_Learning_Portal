"""P09.S4.T3 (COMPAT-01): every test is renderable on the oldest supported client by construction. Forms are built
only from published question versions, and publication refuses a block that the oldest supported renderer
(`blocks.SUPPORTED_RENDERER`) can't show unless a reviewed fallback is attached (§5.4 rule 4). Fixture data only."""

from __future__ import annotations

import copy
from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from tests.test_attempts import _learner
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs
from tests.test_mcq_items import CHECKS, VALID, _new_mcq, _save


def test_a_question_the_oldest_client_cannot_render_never_reaches_a_test(client: TestClient) -> None:
    with get_sessionmaker()() as db:
        scope = {"grades": [11], "subjects": ["biology"]}
        author = Staff(client, db, ["content_author"], scope)
        reviewer = Staff(client, db, ["subject_reviewer"], scope)
        publisher = Staff(client, db, ["publisher"], scope, mfa=True)
        chapter, doc = _chapter(db, 11, "biology", 9)  # not Chemistry 11: its rights must stay unverified
        _confirm_rights(client, db, doc)
    learner = _learner(client)

    def available() -> int:
        url = "/v1/practice/availability?grade=11&subject=biology"
        chapters = client.get(url, headers=learner.headers).json()["chapters"]
        return next(c["questions"] for c in chapters if c["chapter_id"] == str(chapter.id))

    before = available()
    item = _new_mcq(client, author, str(chapter.id))
    body: dict[str, Any] = copy.deepcopy(VALID)
    body["stem"] = [
        {"type": "paragraph", "text": "Fixture stem with an equation."},
        {"type": "equation", "latex": "PV = nRT", "text_alt": "P V equals n R T"},  # needs renderer 2
    ]
    assert _save(client, author, item, body, _refs(chapter, doc)).status_code == 200
    assert _post(client, author, item["id"], "submit").status_code == 200
    review = {"decision": "approve", "comment": "Fixture check", "checklist": CHECKS}
    assert _post(client, reviewer, item["id"], "review", review).status_code == 200
    refused = _post(client, publisher, item["id"], "publish")
    assert refused.status_code == 422 and any("fallback" in e for e in refused.json()["errors"]), refused.text
    assert available() == before  # unpublished, so no practice test or mock can include it
