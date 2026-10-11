"""P07.S1.T1 (LESSON-BLOCKS-01): structured lesson blocks. Worked examples, diagrams and downloadable handouts join
the registered types (explanation = paragraph/heading/list, formula = equation, table, warning = callout, practice
prompt = checkpoint). Diagrams and handouts name archived asset versions (ASSETS-01) of the same class and subject;
learners receive only assets named by a live lesson's published version, under that lesson's access tier.
Technical fixture content only."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from portal_api.modules.content import blocks
from tests.test_assets import _asset, _upload
from tests.test_attempts import _learner
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _create, _post, _refs, _save
from tests.test_data_minimisation import _jpeg_with_gps
from tests.test_evidence import _pdf

BIO11 = {"grades": [11], "subjects": ["biology"]}
EXAMPLE = {
    "type": "example",
    "title": "Fixture worked example",
    "problem": "Fixture problem statement.",
    "steps": ["Fixture step one.", "Fixture step two."],
    "answer": "Fixture answer.",
}


def test_the_new_block_types_are_registered_for_the_oldest_clients() -> None:
    for kind in ("example", "diagram", "handout"):
        spec = blocks.REGISTRY[kind]
        assert all(spec.min_renderer[p] <= blocks.SUPPORTED_RENDERER[p] for p in blocks.PLATFORMS), kind
    ok = blocks.validate_body({"blocks": [EXAMPLE]}, for_publication=True)
    assert ok.errors == [] and ok.block_types == ["example"]
    no_steps = blocks.validate_body({"blocks": [{**EXAMPLE, "steps": []}]}, for_publication=False)
    assert no_steps.errors
    no_alt = {"type": "diagram", "asset_version_id": "00000000-0000-0000-0000-000000000000", "caption": "Fixture"}
    assert blocks.validate_body({"blocks": [no_alt]}, for_publication=False).errors  # alt text is required
    html = {**EXAMPLE, "problem": "<script>alert(1)</script>"}
    assert blocks.validate_body({"blocks": [html]}, for_publication=False).errors == []  # stored as plain text


def _staff(client: TestClient, db: Session) -> dict[str, Staff]:
    return {
        "author": Staff(client, db, ["content_author"], BIO11),
        "author12": Staff(client, db, ["content_author"], {"grades": [12], "subjects": ["biology"]}),
        "reviewer": Staff(client, db, ["subject_reviewer"], BIO11),
        "publisher": Staff(client, db, ["publisher"], BIO11, mfa=True),
    }


def _publish(client: TestClient, team: dict[str, Staff], item: dict[str, Any]) -> Any:
    assert _post(client, team["author"], item["id"], "submit").status_code == 200
    review = {"decision": "approve", "comment": "Fixture check against source pages"}
    assert _post(client, team["reviewer"], item["id"], "review", review).status_code == 200
    return _post(client, team["publisher"], item["id"], "publish")


def test_diagrams_and_handouts_reach_learners_only_through_their_lesson(client: TestClient, db: Session) -> None:
    team = _staff(client, db)
    chapter, doc = _chapter(db, 11, "biology", 4)
    _confirm_rights(client, db, doc)
    image = _upload(client, team["author"], _asset(client, team["author"], "image")["id"], _jpeg_with_gps()).json()
    handout = _upload(client, team["author"], _asset(client, team["author"], "handout")["id"], _pdf(1)).json()
    unrelated = _upload(client, team["author"], _asset(client, team["author"], "image")["id"], _jpeg_with_gps()).json()
    other = Staff(client, db, ["content_author"], {"grades": [12], "subjects": ["biology"]})
    body = {"kind": "image", "title": "Fixture XII", "grade": 12, "subject": "biology"}
    xii_asset = client.post("/v1/studio/assets", headers=other.headers, json=body).json()
    xii = _upload(client, other, xii_asset["id"], _jpeg_with_gps()).json()

    diagram = {"type": "diagram", "asset_version_id": image["id"], "alt": "Fixture labelled cell", "caption": "Fig."}
    sheet = {"type": "handout", "asset_version_id": handout["id"], "title": "Fixture worksheet"}

    # Class XI and XII are never mixed, and a diagram must name an image (not a handout).
    wrong = _create(client, team["author"], chapter, title="Fixture lesson with wrong assets")
    bad = [{**diagram, "asset_version_id": xii["id"]}, {**diagram, "asset_version_id": handout["id"]}]
    assert _save(client, team["author"], wrong, body={"blocks": bad}, refs=_refs(chapter, doc)).status_code == 200
    refused = _publish(client, team, wrong)
    assert refused.status_code == 422, refused.text
    errors = " ".join(refused.json()["errors"])
    assert "Class XII" in errors and "isn't an image" in errors

    lesson = _create(client, team["author"], chapter, title="Fixture lesson with a diagram")
    good = {"blocks": [{"type": "paragraph", "text": "Fixture explanation."}, EXAMPLE, diagram, sheet]}
    assert _save(client, team["author"], lesson, body=good, refs=_refs(chapter, doc)).status_code == 200
    assert _publish(client, team, lesson).status_code == 200
    url = f"/v1/lessons/{lesson['id']}/assets"

    assert client.get(f"{url}/{image['id']}").status_code in (401, 403)  # premium by default: no plan, no file
    learner = _learner(client)
    img = client.get(f"{url}/{image['id']}", headers=learner.headers)
    assert img.status_code == 200 and img.headers["content-type"] == "image/png", img.text
    assert img.headers["x-content-type-options"] == "nosniff" and b"FixtureCam" not in img.content
    pdf = client.get(f"{url}/{handout['id']}", headers=learner.headers)
    assert pdf.status_code == 200 and pdf.headers["content-disposition"].startswith("attachment")
    assert client.get(f"{url}/{unrelated['id']}", headers=learner.headers).status_code == 404  # not in this lesson

    tier = {"tier": "preview", "reason": "Fixture: free sample lesson"}
    assert _post(client, team["publisher"], lesson["id"], "access-tier", tier).status_code == 200
    free = client.get(f"{url}/{image['id']}")
    assert free.status_code == 200 and free.headers["cache-control"].startswith("public")


def test_questions_cannot_carry_handouts(client: TestClient, db: Session) -> None:
    """Handouts belong to lessons; MCQ diagrams are allowed and served through the attempt (QUESTION-DIAGRAMS-01)."""
    import copy

    from tests.test_mcq_items import VALID, _new_mcq

    author = Staff(client, db, ["content_author"], BIO11)
    sheet = _upload(client, author, _asset(client, author, "handout")["id"], _pdf(1)).json()
    chapter, doc = _chapter(db, 11, "biology", 4)
    item = _new_mcq(client, author, str(chapter.id))
    body = copy.deepcopy(VALID)
    body["stem"] = [
        *body["stem"],
        {"type": "handout", "asset_version_id": sheet["id"], "title": "Fixture sheet"},
    ]
    saved = client.put(
        f"/v1/studio/items/{item['id']}/draft",
        headers=author.headers,
        json={"revision": item["working"]["revision"], "body": body, "source_refs": _refs(chapter, doc)},
    )
    assert saved.status_code == 200, saved.text  # drafts may hold work in progress
    submitted = _post(client, author, item["id"], "submit")
    assert submitted.status_code == 422 and any("lessons only" in e for e in submitted.json()["errors"]), submitted.text
