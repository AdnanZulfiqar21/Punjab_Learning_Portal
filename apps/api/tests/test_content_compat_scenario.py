"""P19.S3.T4 (CONTENT-COMPAT-01, acceptance case AC47): new content while old clients are in use.

One scenario, end to end. A learner has a practice test in progress and has downloaded an offline pack. Then an
equation question is published: a block the oldest supported apps can't typeset (it needs renderer 2), so publication
requires a reviewed fallback (static image, alt text and text equivalent; COMPAT-01 covers the refusal without one).

* The test in progress is unaffected: its frozen questions and versions don't change.
* The oldest app's pack format still downloads. Packs don't carry images yet, so a question whose block needs a
  fallback image is left out and counted (`questions_online_only`), and the app says it is online only: a clear
  restriction, never a broken render.
* A new test built for the oldest app delivers the same fallback with the block, which the oldest renderer shows.
* An app below an enforced minimum gets the update-required state before anything starts (CLIENTS-01), never a broken
  render; the minimum-raise notice period and mock windows are covered in `test_client_policy.py`.

Technical fixture questions, a fixture image and labelled fixture accounts only.
"""

from __future__ import annotations

import copy
import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from portal_api.modules.content import blocks, packs
from tests.test_attempts import _learner
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs
from tests.test_mcq_items import CHECKS, VALID, _new_mcq, _save

SCOPE = {"grades": [11], "subjects": ["biology"]}
CHAPTER_INDEX = 10  # no other module publishes into this Biology XI chapter


def _publish(client: TestClient, team: dict[str, Staff], chapter: Any, doc: Any, body: dict[str, Any]) -> str:
    item = _new_mcq(client, team["author"], str(chapter.id))
    saved = _save(client, team["author"], item, body, _refs(chapter, doc))
    assert saved.status_code == 200, saved.text
    assert _post(client, team["author"], item["id"], "submit").status_code == 200
    review = {"decision": "approve", "comment": "Fixture check", "checklist": CHECKS}
    assert _post(client, team["reviewer"], item["id"], "review", review).status_code == 200
    published = _post(client, team["publisher"], item["id"], "publish")
    assert published.status_code == 200, published.text
    return str(item["id"])


def _form(client: TestClient, learner: Staff, chapter: Any, count: int, headers: dict[str, str] | None = None) -> Any:
    return client.post(
        "/v1/practice/forms",
        headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex, **(headers or {})},
        json={"grade": 11, "subject": "biology", "chapter_ids": [str(chapter.id)], "question_count": count},
    )


def test_new_blocks_reach_old_clients_as_fallbacks_and_leave_active_work_alone(client: TestClient, db: Session) -> None:
    from tests.test_assets import _asset, _upload
    from tests.test_data_minimisation import _jpeg_with_gps

    team = {
        "author": Staff(client, db, ["content_author"], SCOPE),
        "reviewer": Staff(client, db, ["subject_reviewer"], SCOPE),
        "publisher": Staff(client, db, ["publisher"], SCOPE, mfa=True),
    }
    chapter, doc = _chapter(db, 11, "biology", CHAPTER_INDEX)
    _confirm_rights(client, db, doc)
    plain = _publish(client, team, chapter, doc, copy.deepcopy(VALID))

    # Before: a test in progress and an offline pack, both on the old content.
    learner = _learner(client)
    form = _form(client, learner, chapter, 1)
    assert form.status_code == 201, form.text
    started = client.post(f"/v1/practice/forms/{form.json()['id']}/attempt", headers=learner.headers)
    assert started.status_code == 200, started.text
    attempt = started.json()
    old_pack = client.get(f"/v1/me/study-packs/{chapter.id}", params={"format": 1}, headers=learner.headers)
    assert old_pack.status_code == 200 and old_pack.json()["manifest"]["pack_format_version"] == 1

    # A new block the oldest apps can't render natively is published, with its reviewed fallback.
    assert blocks.needs_fallback("equation")
    image = _upload(client, team["author"], _asset(client, team["author"], "image")["id"], _jpeg_with_gps()).json()
    fallback = {"text": "P V = n R T", "image_asset_id": image["id"], "alt": "Fixture equation image", "reviewed": True}
    body = copy.deepcopy(VALID)
    body["stem"] = [
        {"type": "paragraph", "text": "Fixture stem with an equation."},
        {"type": "equation", "latex": "PV = nRT", "text_alt": "P V equals n R T", "fallback": fallback},
    ]
    equation = _publish(client, team, chapter, doc, body)

    # The test in progress is unaffected: same questions, same versions, nothing new mixed in.
    now = client.get(f"/v1/attempts/{attempt['id']}", headers=learner.headers).json()
    assert [(i["position"], i.get("version_id"), i["stem"]) for i in now["items"]] == [
        (i["position"], i.get("version_id"), i["stem"]) for i in attempt["items"]
    ]
    assert all(b["type"] != "equation" for i in now["items"] for b in i["stem"])

    # The oldest app's pack format still downloads; the image-backed question is online only, and the pack says so.
    assert packs.PACK_FORMAT_VERSION == 1  # raising it is the explicit, tested "update the app" path
    pack = client.get(f"/v1/me/study-packs/{chapter.id}", params={"format": 1}, headers=learner.headers)
    assert pack.status_code == 200, pack.text
    packed = {q["id"] for q in json.loads(pack.json()["content"])["questions"]}
    assert plain in packed and equation not in packed
    assert pack.json()["manifest"]["questions_online_only"] >= 1
    assert old_pack.json()["manifest"]["questions_online_only"] == 0  # nothing was left out before

    # A new test built for the oldest app delivers the block with the same fallback for its renderer to show.
    oldest = {"X-Portal-Platform": "android", "X-Portal-App-Version": "0.1.0"}
    who = _learner(client)
    made = _form(client, who, chapter, 2, oldest)
    assert made.status_code == 201, made.text
    run = client.post(f"/v1/practice/forms/{made.json()['id']}/attempt", headers={**who.headers, **oldest})
    assert run.status_code == 200, run.text
    stems = [b for i in run.json()["items"] for b in i["stem"] if b["type"] == "equation"]
    assert stems and stems[0]["fallback"]["reviewed"] is True and stems[0]["fallback"]["image_asset_id"] == image["id"]
    assert stems[0]["fallback"]["alt"] and stems[0]["fallback"]["text"]
