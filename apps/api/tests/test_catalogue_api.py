"""Curriculum API behaviour on the real imported catalogue (10 owner books, Class XI and XII separate)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from portal_api.modules.curriculum.importer import DEFAULT_REGISTRY

SUBJECTS = ["biology", "chemistry", "physics", "computer_science", "mathematics"]


def test_catalogue_has_two_separate_grades_with_one_book_per_subject(client: TestClient) -> None:
    r = client.get("/v1/catalogue")
    assert r.status_code == 200
    body = r.json()
    assert body["scope_decision"] == "SCOPE-01"
    assert [g["grade"]["number"] for g in body["grades"]] == [11, 12]
    book_ids: dict[tuple[int, str], str] = {}
    for g in body["grades"]:
        assert [s["subject"]["code"] for s in g["subjects"]] == SUBJECTS
        for s in g["subjects"]:
            assert len(s["books"]) == 1, (g["grade"]["code"], s["subject"]["code"])
            book = s["books"][0]
            assert book["source_id"].startswith(f"C{g['grade']['number']}-")
            book_ids[(g["grade"]["number"], s["subject"]["code"])] = book["id"]
    # The same subject in XI and XII is never the same book.
    for subj in SUBJECTS:
        assert book_ids[(11, subj)] != book_ids[(12, subj)]
    assert "public" in r.headers["cache-control"]


def test_subject_alias_resolves_and_out_of_scope_subject_is_404_problem(client: TestClient) -> None:
    maths = client.get("/v1/grades/11/subjects/maths/book").json()
    assert maths["breadcrumb"]["subject"]["code"] == "mathematics"
    assert maths["breadcrumb"]["source_id"] == "C11-MATH"
    r = client.get("/v1/grades/11/subjects/english/book")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["title"] == "NOT_FOUND"
    assert client.get("/v1/grades/10/subjects/physics/book").status_code == 422


def test_class12_science_chapter_numbers_continue_from_class11(client: TestClient) -> None:
    expect = {"biology": (13, 25), "chemistry": (17, 33), "physics": (13, 21)}
    for subj, (first, last) in expect.items():
        nums = [c["number"] for c in client.get(f"/v1/grades/12/subjects/{subj}/book").json()["chapters"]]
        assert nums[0] == first and nums[-1] == last, (subj, nums)
    # Mathematics and Computer Science restart at 1 in Class XII.
    for subj in ("mathematics", "computer_science"):
        assert client.get(f"/v1/grades/12/subjects/{subj}/book").json()["chapters"][0]["number"] == 1


def test_class12_physics_keeps_contents_page_numbering_as_alias(client: TestClient) -> None:
    chapters = client.get("/v1/grades/12/subjects/physics/book").json()["chapters"]
    optics = next(c for c in chapters if c["number"] == 15)
    assert optics["contents_number"] == 3


def test_class11_maths_units_6_to_8_are_present(client: TestClient) -> None:
    chapters = client.get("/v1/grades/11/subjects/mathematics/book").json()["chapters"]
    assert len(chapters) == 14
    for n in (6, 7, 8):
        ch = next(c for c in chapters if c["number"] == n)
        assert ch["status"] == "complete" and ch["topic_count"] > 0


def test_chapter_detail_has_topic_tree_and_traceable_source(client: TestClient) -> None:
    book = client.get("/v1/grades/12/subjects/biology/book").json()
    first = book["chapters"][0]
    r = client.get(f"/v1/chapters/{first['id']}")
    assert r.status_code == 200
    ch = r.json()
    assert ch["breadcrumb"]["grade"]["number"] == 12
    assert ch["title"].lower().startswith("thermoregulation")
    assert ch["content_state"] == "SOURCE_INDEXED"  # structure only; no reviewed teaching material yet
    registry = {s["source_id"]: s for s in json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))["sources"]}
    assert ch["source"]["sha256"] == registry["C12-BIO"]["sha256"]
    assert ch["source"]["pdf_start"] <= ch["source"]["pdf_end"]
    assert ch["topics"] and ch["topics"][0]["number"] == "13.1"
    assert any(t["children"] for t in ch["topics"]), "nested subtopics expected"
    assert ch["previous_chapter_id"] is None and ch["next_chapter_id"] == book["chapters"][1]["id"]
    assert client.get("/v1/chapters/00000000-0000-0000-0000-000000000000").status_code == 404


def test_search_hits_are_labelled_and_grade_filter_isolates(client: TestClient) -> None:
    hits = client.get("/v1/search", params={"q": "kinetic theory"}).json()["hits"]
    assert {h["grade"] for h in hits} == {11, 12}
    only12 = client.get("/v1/search", params={"q": "kinetic theory", "grade": 12}).json()["hits"]
    assert only12 and all(h["grade"] == 12 for h in only12)
    typo = client.get("/v1/search", params={"q": "photosyntesis"}).json()["hits"]
    assert typo and "photosynthesis" in typo[0]["title"].lower()
    exact = client.get("/v1/search", params={"q": "photosynthesis"}).json()["hits"]
    assert all("retrosynthesis" not in h["title"].lower() for h in exact)
    assert client.get("/v1/search", params={"q": "a"}).status_code == 422


def test_correlation_id_is_echoed_or_replaced(client: TestClient) -> None:
    good = "abc123def456"
    r = client.get("/v1/catalogue", headers={"X-Correlation-ID": good})
    assert r.headers["x-correlation-id"] == good
    r = client.get("/v1/catalogue", headers={"X-Correlation-ID": "<script>bad</script>"})
    assert r.headers["x-correlation-id"] != "<script>bad</script>"
    nf = client.get("/v1/grades/11/subjects/english/book", headers={"X-Correlation-ID": good})
    assert nf.json()["correlation_id"] == good


def test_health_readiness_and_runtime_config(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    ready = client.get("/readyz")
    assert ready.status_code == 200 and ready.json()["status"] == "ready"
    cfg = client.get("/v1/runtime-config").json()
    assert cfg["active_grades"] == [11, 12]
    assert set(cfg["active_subjects"]) == set(SUBJECTS)
    assert "database" not in json.dumps(cfg).lower()
