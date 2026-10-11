"""P08.S1.T1 (QUESTION-DIAGRAMS-01): MCQs may carry archived diagrams. A learner fetches them only through their own
attempt: stem and option diagrams while answering; explanation diagrams only once the result is available (key
isolation, P08.S2.T3). Technical fixture content only."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_assets import _asset, _upload
from tests.test_attempts import _learner, _start
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs
from tests.test_data_minimisation import _jpeg_with_gps
from tests.test_mcq_items import CHECKS, VALID, _new_mcq, _save
from tests.test_mistake_notebook import _submit

BIO11 = {"grades": [11], "subjects": ["biology"]}


def _diagram(version_id: str, alt: str) -> dict[str, Any]:
    return {"type": "diagram", "asset_version_id": version_id, "alt": alt, "caption": "Fixture figure"}


def test_question_diagrams_follow_the_attempt_and_key_isolation(client: TestClient, db: Session) -> None:
    author = Staff(client, db, ["content_author"], BIO11)
    reviewer = Staff(client, db, ["subject_reviewer"], BIO11)
    publisher = Staff(client, db, ["publisher"], BIO11, mfa=True)
    chapter, doc = _chapter(db, 11, "biology", 8)
    _confirm_rights(client, db, doc)
    stem_img = _upload(client, author, _asset(client, author, "image")["id"], _jpeg_with_gps()).json()
    why_img = _upload(client, author, _asset(client, author, "image")["id"], _jpeg_with_gps()).json()
    unrelated = _upload(client, author, _asset(client, author, "image")["id"], _jpeg_with_gps()).json()

    item = _new_mcq(client, author, str(chapter.id))
    body = copy.deepcopy(VALID)
    body["stem"] = [*body["stem"], _diagram(stem_img["id"], "Fixture labelled diagram")]
    body["explanation"]["correct"] = [*body["explanation"]["correct"], _diagram(why_img["id"], "Fixture worked figure")]
    assert _save(client, author, item, body, _refs(chapter, doc)).status_code == 200
    assert _post(client, author, item["id"], "submit").status_code == 200
    review = {"decision": "approve", "comment": "Fixture check", "checklist": CHECKS}
    assert _post(client, reviewer, item["id"], "review", review).status_code == 200
    assert _post(client, publisher, item["id"], "publish").status_code == 200, "MCQs may carry diagrams"

    learner, other = _learner(client), _learner(client)
    form = client.post(
        "/v1/practice/forms",
        headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"grade": 11, "subject": "biology", "chapter_ids": [str(chapter.id)], "question_count": 1},
    )
    assert form.status_code == 201, form.text
    attempt = _start(client, learner, form.json()["id"])
    url = f"/v1/attempts/{attempt['id']}/assets"

    stem = client.get(f"{url}/{stem_img['id']}", headers=learner.headers)
    assert stem.status_code == 200 and stem.headers["content-type"] == "image/png"
    assert stem.headers["cache-control"].startswith("private")
    assert client.get(f"{url}/{why_img['id']}", headers=learner.headers).status_code == 404  # not before the result
    assert client.get(f"{url}/{unrelated['id']}", headers=learner.headers).status_code == 404  # not in this test
    assert client.get(f"{url}/{stem_img['id']}", headers=other.headers).status_code == 404  # not their attempt

    _submit(client, learner, attempt["id"])
    assert client.get(f"{url}/{why_img['id']}", headers=learner.headers).status_code == 200  # result available
