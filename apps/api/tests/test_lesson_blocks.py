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


def test_book_errors_mark_printed_passages_and_a_correction_follows() -> None:
    # BOOK-CORRECTION-01: the printed wording stays, its wrong passage is marked, and a correction callout follows.
    para = {"type": "paragraph", "text": "Fixture value printed as 89.53 m.", "book_errors": ["89.53 m"]}
    fix = {"type": "callout", "tone": "correction", "text": "Fixture value is 79.53 m."}
    ok = blocks.validate_body({"blocks": [para, fix]}, for_publication=True)
    assert ok.errors == []
    table = {"type": "table", "caption": "Fixture", "header": ["A"], "rows": [["C10H14"]], "book_errors": ["C10H14"]}
    example = {**EXAMPLE, "steps": ["Fixture step 41 N."], "book_errors": ["41 N"]}
    eq = {"type": "equation", "latex": r"K_p = K_n N", "text_alt": "Fixture Kp = Kn N"}
    eq["book_errors"] = ["Kn N", "K_n N"]  # in the text equivalent and in the LaTeX
    assert blocks.validate_body({"blocks": [table, example, eq]}, for_publication=False).errors == []
    # A printed box (Do You Know) may carry marks; a mark must be text the block shows; a correction box carries none.
    box = {"type": "callout", "tone": "note", "title": "Do You Know?", "text": "Fixture 7.6 on reactor scale."}
    box["book_errors"] = ["reactor scale"]
    assert blocks.validate_body({"blocks": [box]}, for_publication=False).errors == []
    stray = {**para, "book_errors": ["79.53 m"]}
    assert blocks.validate_body({"blocks": [stray]}, for_publication=False).errors
    marked_correction = {**fix, "book_errors": ["79.53 m"]}
    assert blocks.validate_body({"blocks": [marked_correction]}, for_publication=False).errors


def test_tables_name_the_columns_whose_cells_the_book_merges() -> None:
    # TABLE-MERGE-01: shell L spans 2s and 2p; a blank cell in a merged column continues the one above.
    table = {
        "type": "table",
        "caption": "Fixture shells",
        "header": ["Shell", "Subshell"],
        "rows": [["K", "1s"], ["L", "2s"], ["", "2p"]],
        "merged_columns": [0],
    }
    assert blocks.validate_body({"blocks": [table]}, for_publication=True).errors == []
    assert blocks.validate_body({"blocks": [{**table, "merged_columns": [2]}]}, for_publication=False).errors
    assert blocks.validate_body({"blocks": [{**table, "merged_columns": [-1]}]}, for_publication=False).errors
    # The book's own empty cell under a merged one starts a new cell; only merged columns inside the table qualify.
    assert blocks.validate_body({"blocks": [{**table, "merge_starts": [[2, 0]]}]}, for_publication=True).errors == []
    for bad in ([[2, 1]], [[3, 0]], [[-1, 0]]):
        assert blocks.validate_body({"blocks": [{**table, "merge_starts": bad}]}, for_publication=False).errors, bad


def test_code_listings_keep_their_indentation() -> None:
    # CODE-BLOCK-01: a printed program keeps every space; a book's slip in it can be marked like any other text.
    listing = "class Student:\n    def __init__(self, name):\n        self.name = name\n"
    block = {"type": "code", "language": "python", "text": listing, "caption": "Fixture listing"}
    ok = blocks.validate_body({"blocks": [block]}, for_publication=True)
    assert ok.errors == [] and ok.block_types == ["code"]
    parsed = blocks.validate_body({"blocks": [{**block, "book_errors": ["self.name"]}]}, for_publication=False)
    assert parsed.errors == []
    assert blocks.validate_body({"blocks": [{**block, "language": "cobol"}]}, for_publication=False).errors
    assert blocks.validate_body({"blocks": [{**block, "text": ""}]}, for_publication=False).errors
    assert blocks.validate_body({"blocks": [{**block, "book_errors": ["print("]}]}, for_publication=False).errors
    # CODE-RUNNER-01: a program the content tools ran cleanly carries `runnable`; it must be a real boolean.
    assert blocks.validate_body({"blocks": [{**block, "runnable": True}]}, for_publication=True).errors == []
    assert blocks.validate_body({"blocks": [{**block, "runnable": "yes"}]}, for_publication=False).errors


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
    body = {"kind": "image", "title": "Fixture 12", "grade": 12, "subject": "biology"}
    xii_asset = client.post("/v1/studio/assets", headers=other.headers, json=body).json()
    xii = _upload(client, other, xii_asset["id"], _jpeg_with_gps()).json()

    diagram = {"type": "diagram", "asset_version_id": image["id"], "alt": "Fixture labelled cell", "caption": "Fig."}
    sheet = {"type": "handout", "asset_version_id": handout["id"], "title": "Fixture worksheet"}

    # Class 11 and 12 are never mixed, and a diagram must name an image (not a handout).
    wrong = _create(client, team["author"], chapter, title="Fixture lesson with wrong assets")
    bad = [{**diagram, "asset_version_id": xii["id"]}, {**diagram, "asset_version_id": handout["id"]}]
    assert _save(client, team["author"], wrong, body={"blocks": bad}, refs=_refs(chapter, doc)).status_code == 200
    refused = _publish(client, team, wrong)
    assert refused.status_code == 422, refused.text
    errors = " ".join(refused.json()["errors"])
    assert "Class 12" in errors and "isn't an image" in errors

    # ANSWER-FIGURE-01: a self-check's drawn answer is an archived image of the same class, served with the lesson.
    drawn = _upload(client, team["author"], _asset(client, team["author"], "image")["id"], _jpeg_with_gps()).json()
    check = {
        "type": "checkpoint",
        "mode": "self_check",
        "prompt": "Fixture: sketch the graph.",
        "explanation": "Fixture: what the graph shows.",
        "answer_figure": {"asset_version_id": drawn["id"], "alt": "Fixture answer graph", "caption": "Fixture answer"},
    }
    misnamed = _create(client, team["author"], chapter, title="Fixture lesson with a misnamed answer figure")
    wrong_answer = {**check, "answer_figure": {**check["answer_figure"], "asset_version_id": handout["id"]}}
    saved = _save(client, team["author"], misnamed, body={"blocks": [wrong_answer]}, refs=_refs(chapter, doc))
    assert saved.status_code == 200
    refused = _publish(client, team, misnamed)
    assert refused.status_code == 422 and "isn't an image" in " ".join(refused.json()["errors"]), refused.text

    lesson = _create(client, team["author"], chapter, title="Fixture lesson with a diagram")
    good = {"blocks": [{"type": "paragraph", "text": "Fixture explanation."}, EXAMPLE, diagram, sheet, check]}
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
    answer = client.get(f"{url}/{drawn['id']}", headers=learner.headers)
    assert answer.status_code == 200 and answer.headers["content-type"] == "image/png", answer.text
    # P07.S3.T3 (LESSON-SIZE-01): the lesson says what its images and handouts cost to download, before they load.
    listed = client.get(f"/v1/chapters/{chapter.id}/lessons", headers=learner.headers).json()
    mine = next(x for x in listed if x["id"] == lesson["id"])
    assert mine["download_bytes"] == len(img.content) + len(pdf.content) + len(answer.content)
    anonymous = next(x for x in client.get(f"/v1/chapters/{chapter.id}/lessons").json() if x["id"] == lesson["id"])
    assert anonymous["locked"] is True and anonymous["download_bytes"] is None  # nothing to download while locked

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
