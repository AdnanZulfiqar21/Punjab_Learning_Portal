"""P19.S1.T3 (OWNER-OPS-01): owner operations end to end, through the real API, one role per step.

Import → review → publish → a learner answers → quarantine → reviewed correction → regrade → refund (a withdrawn
staff grant until payments exist, B06) → suspension → a trial appeal → the learner's data export. At every handoff
the next person's action is refused to the previous one, so no step relies on a super-admin. Questions, accounts,
grants and appeals are labelled technical fixtures in an otherwise unused Physics XI chapter.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_attempts import _op, _save_ops
from tests.test_content_import import _doc, _preview, _row
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs
from tests.test_mcq_corrections import _keys
from tests.test_mcq_items import CHECKS
from tests.test_trial_claims import _claim, _grants, _install

SCOPE = {"grades": [11], "subjects": ["physics"]}
CHAPTER_INDEX = 7  # not used by any other test module


def _staff(client: TestClient, roles: list[str], scope: dict[str, Any] | None = None, mfa: bool = True) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, roles, scope, mfa)


def _email(who: Staff) -> str:
    return who.email


def test_owner_operations_hand_off_with_the_right_permission_at_every_step(client: TestClient) -> None:
    author = _staff(client, ["content_author"], SCOPE, mfa=False)
    reviewer = _staff(client, ["subject_reviewer"], SCOPE, mfa=False)
    publisher = _staff(client, ["publisher"], SCOPE)
    adjudicator = _staff(client, ["academic_adjudicator"], SCOPE)
    finance, support, admin = _staff(client, ["finance"]), _staff(client, ["support"]), _staff(client, ["owner_admin"])
    learner = _staff(client, [], mfa=False)

    # 1. Import: the author previews and commits two questions as drafts; a learner can't import.
    with get_sessionmaker()() as db:
        chapter, doc = _chapter(db, 11, "physics", CHAPTER_INDEX)
        _confirm_rights(client, db, doc)
        chapter_key, chapter_id, refs = chapter.natural_key, str(chapter.id), _refs(chapter, doc)
    run = uuid.uuid4().hex[:8]
    rows = [_row(f"OPS-{run}-{n}", chapter_key, refs, f"Fixture ops stem {n} {run}") for n in (1, 2)]
    assert _preview(client, learner, _doc(*rows)).status_code == 403
    batch = _preview(client, author, _doc(*rows)).json()
    committed = client.post(f"/v1/studio/imports/{batch['id']}/commit", headers=author.headers)
    assert committed.status_code == 200, committed.text
    items = [row["item_id"] for row in committed.json()["rows"]]

    # 2. Review: the author submits but can't approve; the independent reviewer approves.
    review = {"decision": "approve", "comment": "Fixture check", "checklist": CHECKS}
    for item in items:
        submitted_item = _post(client, author, item, "submit")
        assert submitted_item.status_code == 200, submitted_item.text
        assert _post(client, author, item, "review", review).status_code in (403, 409)
        assert _post(client, reviewer, item, "review", review).status_code == 200
        # 3. Publish: the reviewer can't; the publisher (MFA) does.
        assert _post(client, reviewer, item, "publish").status_code == 403
        assert _post(client, publisher, item, "publish").status_code == 200

    # 4. A learner with a scholarship (finance grants it; support can't) answers both questions correctly.
    grant_body = {
        "email": _email(learner),
        "source": "scholarship",
        "days": 30,
        "written_units": 0,
        "reason": "Fixture: scholarship grant",
    }
    assert client.post("/v1/admin/entitlements", headers=support.headers, json=grant_body).status_code == 403
    grant = client.post("/v1/admin/entitlements", headers=finance.headers, json=grant_body)
    assert grant.status_code == 201, grant.text
    form = client.post(
        "/v1/practice/forms",
        headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"grade": 11, "subject": "physics", "chapter_ids": [chapter_id], "question_count": 2},
    ).json()
    attempt = client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=learner.headers).json()
    keys = _keys(form["id"])
    assert _save_ops(client, learner, attempt["id"], *[_op(p, 1, k) for p, k in keys.items()]).status_code == 200
    submitted = client.post(
        f"/v1/attempts/{attempt['id']}/submit",
        headers=learner.headers,
        json={"idempotency_key": uuid.uuid4().hex, "ops": []},
    )
    assert submitted.status_code == 200
    first = client.get(f"/v1/attempts/{attempt['id']}/result", headers=learner.headers).json()
    assert (first["raw"], first["maximum"], first["version"]) == (2, 2, 1)

    # 5. Quarantine: the author can't; the publisher quarantines the defective question at VOID.
    position_item = {int(p): i for p, i in _positions(form["id"]).items()}
    voided = position_item[1]
    quarantine = {"reason": "Fixture: no valid option", "level": "VOID"}
    assert _post(client, author, voided, "quarantine", quarantine).status_code == 403
    assert _post(client, publisher, voided, "quarantine", quarantine).status_code == 200
    try:
        # 6. Correct: the publisher can't record a score correction; the scoped adjudicator (MFA) does.
        correction = {"defect": "VOID", "reason": "Fixture: confirmed after review"}
        url = f"/v1/studio/items/{voided}/score-corrections"
        assert client.post(url, headers=publisher.headers, json=correction).status_code == 403
        assert client.post(url, headers=adjudicator.headers, json=correction).status_code == 201

        # 7. Regrade: the learner's result is a new score version; the first is kept.
        regraded = client.get(f"/v1/attempts/{attempt['id']}/result", headers=learner.headers).json()
        assert (regraded["raw"], regraded["maximum"], regraded["version"]) == (1, 1, 2)

        # 8. Refund: support can't withdraw a grant; finance does. New tests stop, the result stays.
        revoke = f"/v1/admin/entitlements/{grant.json()['id']}/revoke"
        reason = {"reason": "Fixture: refund issued"}
        assert client.post(revoke, headers=support.headers, json=reason).status_code == 403
        assert client.post(revoke, headers=finance.headers, json=reason).status_code == 200
        refused = client.post(
            "/v1/practice/forms",
            headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex},
            json={"grade": 11, "subject": "physics", "chapter_ids": [chapter_id], "question_count": 1},
        )
        assert refused.status_code == 403 and refused.json()["title"] == "ACCESS_REQUIRED"
        assert client.get(f"/v1/attempts/{attempt['id']}/result", headers=learner.headers).status_code == 200

        # 9. Suspend: finance can't; the administrator suspends an abusive account, whose token then stops working.
        abuser = _staff(client, [], mfa=False)
        suspend = f"/v1/admin/users/{abuser.id}/suspend"
        assert client.post(suspend, headers=finance.headers, json={"reason": "Fixture: abuse"}).status_code == 403
        assert client.post(suspend, headers=admin.headers, json={"reason": "Fixture: abuse"}).status_code == 200
        assert client.get("/v1/me", headers=abuser.headers).status_code in (401, 403)

        # 10. Trial appeal: a falsely blocked learner; finance can't decide it, support's reviewer grants an exception.
        appellant, install = _staff(client, [], mfa=False), _install()
        assert _claim(client, appellant, install, verdict="consumed").json()["state"] == "device_used"
        exception = {"email": appellant.email, "surface": "android", "days": 7, "reason": "Fixture: receipt seen"}
        assert client.post("/v1/staff/trial/exceptions", headers=finance.headers, json=exception).status_code == 403
        assert client.post("/v1/staff/trial/exceptions", headers=support.headers, json=exception).status_code == 201
        assert _claim(client, appellant, install, verdict="consumed").json()["state"] == "granted"
        assert _grants(appellant) == 1

        # 11. Export: the learner's own data, including both score versions and the withdrawn grant; nobody else's.
        exported = client.get("/v1/me/data-export", headers=learner.headers)
        assert exported.status_code == 200
        data = json.loads(exported.content)
        versions = sorted(s["version"] for s in data["practice"]["scores"] if s["attempt_id"] == attempt["id"])
        assert versions == [1, 2]
        assert any(e["status"] == "revoked" for e in data["access"])
        assert appellant.email not in exported.text and abuser.email not in exported.text
    finally:
        with get_sessionmaker()() as db:
            db.execute(text("update mcq_adjudication set status = 'superseded' where item_id = :i"), {"i": voided})
            db.commit()
        _post(client, publisher, voided, "release", {"reason": "Fixture cleanup"})


def _positions(form_id: str) -> dict[int, str]:
    with get_sessionmaker()() as db:
        rows = db.execute(text("select position, item_id from form_item where form_id = :f"), {"f": form_id}).all()
        return {int(p): str(i) for p, i in rows}
