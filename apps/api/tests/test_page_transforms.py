"""W03.S1.T3 (TRANSFORMS-01): conservative page transformations.

A learner may turn a page, trim its edges or ask for a higher-contrast preview before submitting. The original is
never changed: the preview is re-rendered from it with the transform, regions on the page map back to the original,
and a marker can always see the untouched original. The transforms are lossless or monotonic, so faint ink, pencil,
small marks and lines at the edge survive them. Every image is a labelled synthetic technical fixture.
"""

from __future__ import annotations

import hashlib
import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from portal_api.modules.written import evidence, storage
from tests.test_written_attempts import _learner, _map, _seal, _start, _upload
from tests.test_written_marking import _case_for, _reviewer

PAPER, INK, PENCIL = 225, 40, 200


def _fixture_page() -> Image.Image:
    """Synthetic page: dark writing, a faint pencil stroke, a 3 px superscript-sized mark and a line on the edge."""
    im = Image.new("L", (900, 1200), PAPER)
    d = ImageDraw.Draw(im)
    d.line((100, 200, 700, 200), fill=INK, width=4)  # ink
    d.line((100, 400, 700, 400), fill=PENCIL, width=2)  # faint pencil
    d.rectangle((500, 600, 502, 602), fill=INK)  # a superscript-sized mark
    d.line((0, 0, 0, 1199), fill=INK, width=1)  # a diagram line on the very edge
    return im


def _marks(im: Image.Image) -> int:
    """Pixels darker than this image's own paper (its most common shade): anything mark-bearing."""
    hist = im.convert("L").histogram()
    paper = max(range(256), key=lambda v: hist[v])
    return sum(hist[: paper - 5])


def _png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize(
    ("rotate", "derived", "source"),
    [
        (0, [0.1, 0.2, 0.3, 0.4], [0.1, 0.2, 0.3, 0.4]),
        (90, [0.0, 0.0, 0.5, 0.25], [0.0, 0.5, 0.25, 0.5]),  # top-left of the turned page = bottom-left of the original
        (180, [0.0, 0.0, 0.5, 0.25], [0.5, 0.75, 0.5, 0.25]),
        (270, [0.0, 0.0, 0.5, 0.25], [0.75, 0.0, 0.25, 0.5]),
    ],
)
def test_regions_on_a_turned_page_map_back_to_the_original(
    rotate: int, derived: list[float], source: list[float]
) -> None:
    assert evidence.to_source(derived, {"rotate": rotate}) == pytest.approx(source)
    # With a trim, the place lands inside the kept part of the original.
    trimmed = evidence.to_source([0.0, 0.0, 1.0, 1.0], {"crop": [0.1, 0.2, 0.5, 0.6]})
    assert trimmed == pytest.approx([0.1, 0.2, 0.5, 0.6])


def test_transforms_are_checked() -> None:
    for bad in ({"rotate": 45}, {"crop": [0, 0, 0.2, 1]}, {"crop": [0.8, 0, 0.5, 1]}, {"crop": ["x", 0, 1, 1]}):
        with pytest.raises(evidence.Rejected):
            evidence.check_transform(bad)
    assert evidence.check_transform({"crop": [0, 0, 1, 1]})["crop"] is None  # a trim of nothing is no trim
    assert evidence.check_transform(None) == {"rotate": 0, "crop": None, "enhance": False}


def test_turning_and_clarifying_keep_every_mark() -> None:
    page = _fixture_page()
    for transform in (
        {"rotate": 90},
        {"rotate": 180},
        {"rotate": 270},
        {"enhance": True},
        {"rotate": 90, "enhance": True},
    ):
        shown = evidence.apply_transform(page, transform)
        assert _marks(shown) >= _marks(page), transform  # nothing mark-bearing becomes paper
    clear = evidence.apply_transform(page, {"enhance": True})
    assert clear.getpixel((400, 400)) < clear.getpixel((400, 300))  # the faint pencil stays darker than the paper
    assert clear.getpixel((0, 600)) < clear.getpixel((10, 600))  # so does the line on the edge
    assert clear.getpixel((501, 601)) < clear.getpixel((520, 601))  # and the small mark
    turned = evidence.apply_transform(page, {"rotate": 90})
    assert turned.size == (1200, 900)


def test_the_worker_renders_a_page_with_its_transform() -> None:
    data = _png(_fixture_page())
    plain = evidence.render_page(data, "image/png", 1, None)
    turned = evidence.render_page(data, "image/png", 1, {"rotate": 90})
    assert (turned.width, turned.height) == (plain.height, plain.width)
    trimmed = evidence.render_page(data, "image/png", 1, {"crop": [0.0, 0.0, 0.5, 0.5]})
    assert trimmed.width < plain.width and trimmed.height < plain.height


def test_a_learner_transforms_a_page_and_the_original_is_kept(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner = _learner(client)
    attempt = _start(client, learner, published_written["chapter"])
    up = _upload(client, learner, attempt["id"], _png(_fixture_page())).json()["pages"][0]
    url = f"/v1/written-attempts/{attempt['id']}/pages/{up['id']}/transform"

    refused = client.put(url, headers=learner.headers, json={"crop": [0, 0, 0.1, 0.1]})
    assert refused.status_code == 422 and refused.json()["code_reason"] == "TRANSFORM_REFUSED"
    assert client.put(url, headers=_learner(client).headers, json={"rotate": 90}).status_code == 404  # not theirs

    turned = client.put(url, headers=learner.headers, json={"rotate": 90, "enhance": True})
    assert turned.status_code == 200, turned.text
    page = turned.json()
    assert (page["width"], page["height"]) == (up["height"], up["width"])
    assert page["transform"] == {
        "rotate": 90,
        "crop": None,
        "enhance": True,
        "straighten": 0.0,  # STRAIGHTEN-01: not straightened
        "aspect": None,
        "shown_crop": None,
    }
    shown = client.get(f"/v1/written-attempts/{attempt['id']}", headers=learner.headers).json()["pages"][0]
    assert shown["transform"]["rotate"] == 90

    # A trim of the turned page as shown: its left half is the bottom half of the original photo.
    half = {"rotate": 90, "enhance": True, "trim": [0, 0, 0.5, 1]}
    trimmed = client.put(url, headers=learner.headers, json=half)
    assert trimmed.status_code == 200, trimmed.text
    assert trimmed.json()["transform"]["crop"] == [0.0, 0.5, 1.0, 0.5] and trimmed.json()["width"] < page["width"]
    again = client.put(url, headers=learner.headers, json=half)  # a quarter of the original height is too little
    assert again.status_code == 422 and again.json()["code_reason"] == "TRANSFORM_REFUSED"
    untrimmed = client.put(url, headers=learner.headers, json={"rotate": 90, "enhance": True, "crop": None})
    assert untrimmed.json()["transform"]["crop"] is None and untrimmed.json()["width"] == page["width"]

    # Submitted: the transform is fixed, and the marker can see the page as shown or the untouched original.
    m = _map(client, learner, attempt, {"1:a": {"pages": [up["id"]]}, "1:b": {"unanswered": True}}).json()
    assert _seal(client, learner, attempt["id"], m["manifest_revision"]).status_code == 200
    assert client.put(url, headers=learner.headers, json={"rotate": 0}).status_code in (409, 422)

    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, attempt["id"])
    client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)
    detail = f"/v1/studio/written/cases/{case['id']}/pages/{up['id']}/detail"
    as_shown = client.get(detail, headers=reviewer.headers)
    original = client.get(detail, headers=reviewer.headers, params={"original": "true"})
    assert as_shown.status_code == 200 and original.status_code == 200
    w_shown, h_shown = Image.open(io.BytesIO(as_shown.content)).size
    w_orig, h_orig = Image.open(io.BytesIO(original.content)).size
    assert w_shown > h_shown and h_orig > w_orig  # the original is the upright, untouched photo
    assert "view=original" in original.headers["x-derivative"] and "view=as-shown" in as_shown.headers["x-derivative"]
    # The stored original is byte-for-byte what was uploaded.
    stored = storage.get_store()
    from portal_api.db import get_sessionmaker
    from portal_api.modules.written.models import WrittenFile

    with get_sessionmaker()() as db:
        f = db.get(WrittenFile, up["file_id"])
        assert f is not None
        assert hashlib.sha256(stored.get(f.storage_key)).hexdigest() == f.sha256
