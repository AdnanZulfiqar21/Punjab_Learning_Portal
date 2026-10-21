"""W03.S2.T2 (REGION-MAP-01): page and question mapping.

An answer can mark the area of a page it is on, kept in the original page's coordinates so turning or trimming the page
doesn't move it; a page shared by several answers needs either areas or the learner's confirmation that the question
numbers are written on it; the learner can put the pages in order; and every saved mapping is kept as a revision.
Pages are synthetic technical fixtures.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from portal_api.modules.written import evidence
from tests.test_written_attempts import _learner, _png, _seal, _start, _upload
from tests.test_written_marking import _case_for, _reviewer


def _put(client: TestClient, who: Any, attempt: dict[str, Any], **body: Any) -> Any:
    return client.put(
        f"/v1/written-attempts/{attempt['id']}/manifest",
        headers=who.headers,
        json={"expected_revision": attempt["manifest_revision"], **body},
    )


def _one_page(client: TestClient, published_written: dict[str, Any], seed: int) -> tuple[Any, dict[str, Any], str]:
    who = _learner(client)
    a = _start(client, who, published_written["chapter"])
    page = _upload(client, who, a["id"], _png(seed=seed)).json()["pages"][0]["id"]
    return who, a, page


def test_view_regions_and_canonical_regions_are_inverses() -> None:
    for transform in ({"rotate": 90}, {"rotate": 180}, {"rotate": 270}, {"crop": [0.1, 0.1, 0.8, 0.7], "rotate": 90}):
        for box in ([0.0, 0.0, 0.5, 0.25], [0.2, 0.3, 0.4, 0.4]):
            assert evidence.from_source(evidence.to_source(box, transform), transform) == pytest.approx(box)
    # Straightened: the shown area always contains the marked one.
    t = {"straighten": 3.0, "aspect": 0.75}
    shown = evidence.from_source(evidence.to_source([0.3, 0.3, 0.2, 0.1], t), t)
    assert shown[0] <= 0.3 and shown[1] <= 0.3 and shown[0] + shown[2] >= 0.5 and shown[1] + shown[3] >= 0.4
    # An area trimmed away isn't shown.
    assert evidence.from_source([0.0, 0.0, 0.05, 0.05], {"crop": [0.5, 0.5, 0.5, 0.5]}) == [0.0, 0.0, 0.0, 0.0]


def test_an_area_is_kept_on_the_original_page_and_follows_turns(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    who, a, page = _one_page(client, published_written, seed=31)
    url = f"/v1/written-attempts/{a['id']}/pages/{page}/transform"
    assert client.put(url, headers=who.headers, json={"rotate": 90}).status_code == 200

    m = _put(client, who, a, slots={"1:a": {"pages": [page], "regions": [{"page": page, "box": [0, 0, 0.5, 0.25]}]}})
    assert m.status_code == 200, m.text
    region = m.json()["manifest"]["slots"]["1:a"]["regions"][0]
    assert region["source"] == pytest.approx([0.0, 0.5, 0.25, 0.5])  # the bottom-left of the upright original
    assert region["box"] == pytest.approx([0.0, 0.0, 0.5, 0.25])  # where the learner drew it

    # Turning the page back moves where it is shown, not what it marks.
    assert client.put(url, headers=who.headers, json={"rotate": 0}).status_code == 200
    shown = client.get(f"/v1/written-attempts/{a['id']}", headers=who.headers).json()
    region = shown["manifest"]["slots"]["1:a"]["regions"][0]
    assert region["box"] == pytest.approx([0.0, 0.5, 0.25, 0.5]) == region["source"]


def test_areas_are_checked_and_kept_by_clients_that_dont_send_them(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    who, a, page = _one_page(client, published_written, seed=32)
    area = {"page": page, "box": [0.1, 0.1, 0.5, 0.3]}
    m = _put(client, who, a, slots={"1:a": {"pages": [page], "regions": [area]}}).json()

    kept = _put(client, who, m, slots={"1:a": {"pages": [page]}, "1:b": {"unanswered": True}})
    assert kept.status_code == 200
    assert kept.json()["manifest"]["slots"]["1:a"]["regions"][0]["source"] == pytest.approx([0.1, 0.1, 0.5, 0.3])
    returned = kept.json()["manifest"]["slots"]["1:a"]["regions"][0]
    unchanged = _put(
        client,
        who,
        kept.json(),
        slots={"1:a": {"pages": [page], "regions": [{"page": page, "source": returned["source"]}]}},
    )
    assert unchanged.json()["manifest"]["slots"]["1:a"]["regions"][0]["source"] == returned["source"]
    # A client that sends an area back as it came (source and box) keeps the saved place, never the shown one.
    echoed = _put(
        client,
        who,
        unchanged.json(),
        slots={"1:a": {"pages": [page], "regions": [{**returned, "box": [0.0, 0.0, 0.9, 0.9]}]}},
    )
    assert echoed.json()["manifest"]["slots"]["1:a"]["regions"][0]["source"] == returned["source"]
    cleared = _put(client, who, echoed.json(), slots={"1:a": {"pages": [page], "regions": []}})
    assert (
        "regions" not in cleared.json()["manifest"]["slots"]["1:a"]
        or not cleared.json()["manifest"]["slots"]["1:a"]["regions"]
    )

    bad = {
        "1:a": {"pages": [page], "regions": [{"page": page, "box": [0.5, 0.5, 0.01, 0.2]}]},  # too thin
        "1:b": {"pages": [], "regions": [{"page": page, "box": [0, 0, 0.5, 0.5]}]},  # a page it doesn't use
    }
    refused = _put(client, who, cleared.json(), slots=bad)
    assert refused.status_code == 422 and len(refused.json()["errors"]) == 2
    outside = _put(
        client,
        who,
        cleared.json(),
        slots={"1:a": {"pages": [page], "regions": [{"page": page, "box": [0.8, 0, 0.5, 1]}]}},
    )
    assert outside.status_code == 422
    many = [{"page": page, "box": [0.0, i * 0.05, 0.5, 0.05]} for i in range(11)]
    assert _put(client, who, cleared.json(), slots={"1:a": {"pages": [page], "regions": many}}).status_code == 422


def test_a_shared_page_needs_areas_or_confirmed_numbering_before_submitting(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    who, a, page = _one_page(client, published_written, seed=33)
    shared = _put(client, who, a, slots={"1:a": {"pages": [page]}, "1:b": {"pages": [page]}}).json()
    assert shared["manifest"]["ambiguous"] == [page]
    refused = _seal(client, who, a["id"], shared["manifest_revision"])
    assert refused.status_code == 422 and refused.json()["code_reason"] == "NUMBERING_UNCONFIRMED"
    assert refused.json()["pages"] == [page]

    # Marking both answers' areas settles it ...
    areas = _put(
        client,
        who,
        shared,
        slots={
            "1:a": {"pages": [page], "regions": [{"page": page, "box": [0, 0, 1, 0.5]}]},
            "1:b": {"pages": [page], "regions": [{"page": page, "box": [0, 0.5, 1, 0.5]}]},
        },
    ).json()
    assert areas["manifest"]["ambiguous"] == []
    # ... and so does confirming the numbering; a confirmation is dropped once the page is no longer shared.
    confirmed = _put(
        client, who, areas, slots={"1:a": {"pages": [page], "regions": []}, "1:b": {"pages": [page]}}, confirmed=[page]
    ).json()
    assert confirmed["manifest"]["ambiguous"] == [] and confirmed["manifest"]["confirmed"] == [page]
    alone = _put(client, who, confirmed, slots={"1:a": {"pages": [page]}, "1:b": {"unanswered": True}}).json()
    assert alone["manifest"]["confirmed"] == []
    again = _put(client, who, alone, slots={"1:a": {"pages": [page]}, "1:b": {"pages": [page]}}).json()
    assert again["manifest"]["ambiguous"] == [page]  # a stale confirmation doesn't carry over
    final = _put(
        client, who, again, slots={"1:a": {"pages": [page]}, "1:b": {"pages": [page]}}, confirmed=[page]
    ).json()
    assert _seal(client, who, a["id"], final["manifest_revision"]).status_code == 200


def test_pages_can_be_put_in_order_and_reviewers_see_it_with_the_areas(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    who = _learner(client)
    a = _start(client, who, published_written["chapter"])
    p1 = _upload(client, who, a["id"], _png(seed=34)).json()["pages"][0]["id"]
    p2 = _upload(client, who, a["id"], _png(seed=35)).json()["pages"][0]["id"]
    assert [p["id"] for p in client.get(f"/v1/written-attempts/{a['id']}", headers=who.headers).json()["pages"]] == [
        p1,
        p2,
    ]

    slots = {
        "1:a": {"pages": [p2, p1], "regions": [{"page": p1, "box": [0, 0.5, 1, 0.5]}]},
        "1:b": {"unanswered": True},
    }
    assert _put(client, who, a, slots=slots, order=[p1]).status_code == 422  # every page once
    assert _put(client, who, a, slots=slots, order=[p2, p2, p1]).status_code == 422
    m = _put(client, who, a, slots=slots, order=[p2, p1])
    assert m.status_code == 200, m.text
    assert [p["id"] for p in m.json()["pages"]] == [p2, p1]
    assert _seal(client, who, a["id"], m.json()["manifest_revision"]).status_code == 200

    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, a["id"])
    detail = client.get(f"/v1/studio/written/cases/{case['id']}", headers=reviewer.headers).json()
    assert [p["id"] for p in detail["pages"]] == [p2, p1]
    region = detail["manifest"]["slots"]["1:a"]["regions"][0]
    assert region["page"] == p1 and region["box"] == pytest.approx([0.0, 0.5, 1.0, 0.5])


def test_every_saved_mapping_is_kept(client: TestClient, published_written: dict[str, Any]) -> None:
    who, a, page = _one_page(client, published_written, seed=36)
    m1 = _put(client, who, a, slots={"1:a": {"pages": [page]}}).json()
    m2 = _put(
        client, who, m1, slots={"1:a": {"pages": [page], "regions": [{"page": page, "box": [0, 0, 1, 1]}]}}
    ).json()
    _put(client, who, m2, slots={"1:a": {"pages": [page]}, "1:b": {"unanswered": True}})
    url = f"/v1/written-attempts/{a['id']}/manifest/revisions"
    revisions = client.get(url, headers=who.headers).json()
    assert [(r["revision"], r["answered"], r["unanswered"], r["areas"]) for r in revisions] == [
        (1, 1, 0, 0),
        (2, 1, 0, 1),
        (3, 1, 1, 1),  # the area stays: the third save didn't send areas
    ]
    assert client.get(url, headers=_learner(client).headers).status_code == 404
