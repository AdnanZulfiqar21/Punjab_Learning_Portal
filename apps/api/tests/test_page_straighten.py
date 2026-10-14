"""W03.S1.T3 (STRAIGHTEN-01): straightening a crooked page photo (deskew), as a conservative transform.

* The angle is found from the writing itself (projection profile) and only within ±10 degrees.
* Straightening samples nearest-neighbour: every pixel shown is a pixel of the original, or paper white where the
  turn reveals a corner, so nothing is blended lighter and faint strokes keep their darkness; nothing is cut off.
* Regions on the straightened page (markers' feedback places, detail views, trims) map back to the original.
* It is offered only where rolled out (`page_straighten`): deployed roles start at 0% until it is qualified on real
  faint-ink and pencil scripts (B10). Undo is always possible, and markers can always see the untouched original.

Every image is a labelled synthetic technical fixture.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.written import evidence
from tests.test_written_attempts import _learner, _map, _seal, _start, _upload
from tests.test_written_marking import _case_for, _reviewer

PAPER, INK, PENCIL = 245, 30, 190


def _writing(width: int = 1000, height: int = 1300) -> Image.Image:
    """Synthetic handwriting stand-in: 22 lines of word-like strokes, and one faint pencil line."""
    im = Image.new("L", (width, height), PAPER)
    d = ImageDraw.Draw(im)
    for row in range(22):
        y = 80 + row * 52
        x = 70
        while x < width - 120:
            word = 40 + (x * 7 + row * 13) % 90
            d.rectangle((x, y, x + word, y + 14), fill=INK)
            x += word + 22
    d.line((70, height - 60, width - 70, height - 60), fill=PENCIL, width=1)
    return im


def _tilted(angle: float) -> Image.Image:
    return _writing().rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=PAPER)


def _png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("tilt", [4.0, -3.0, 7.5])
def test_the_angle_that_levels_the_writing_is_found(tilt: float) -> None:
    found = evidence.estimate_skew(_tilted(tilt))
    assert abs(found + tilt) <= 0.3, (tilt, found)  # the correction undoes the tilt


def test_a_level_or_empty_page_is_left_alone() -> None:
    assert evidence.estimate_skew(_writing()) == 0.0
    assert evidence.estimate_skew(Image.new("L", (800, 1000), PAPER)) == 0.0


def test_straightening_shows_only_original_pixels_and_keeps_faint_strokes() -> None:
    im = Image.new("L", (900, 1200), PAPER)
    d = ImageDraw.Draw(im)
    for i in range(12):  # thin faint strokes in many directions, like pencil working
        d.line((60 + i * 60, 100, 120 + i * 55, 1100 - i * 40), fill=PENCIL, width=2)
    d.line((60, 600, 840, 620), fill=INK, width=1)  # a 1 px ink line
    out = evidence._straighten(im, 3.7)
    assert out.width >= im.width and out.height >= im.height  # nothing is cut off
    assert set(out.get_flattened_data()) <= set(im.get_flattened_data()) | {
        255
    }  # every pixel is an original pixel, or new paper
    before = sum(1 for v in im.get_flattened_data() if v < 230)
    after = sum(1 for v in out.get_flattened_data() if v < 230)
    assert 0.9 <= after / before <= 1.1, (before, after)  # faint strokes keep their darkness and extent


@pytest.mark.parametrize("shown_crop", [None, [0.1, 0.08, 0.8, 0.85]])
def test_regions_on_a_straightened_page_map_back_to_the_original(shown_crop: list[float] | None) -> None:
    original = Image.new("L", (1200, 900), PAPER)
    dot = (830, 260)  # a single mark, somewhere inside the kept part
    ImageDraw.Draw(original).rectangle((dot[0] - 3, dot[1] - 3, dot[0] + 3, dot[1] + 3), fill=0)
    asked = {"rotate": 90, "crop": [0.1, 0.05, 0.8, 0.9], "enhance": False}
    level = evidence.apply_transform(original, asked)
    t = {**asked, "straighten": 6.0, "aspect": level.width / level.height, "shown_crop": shown_crop}
    shown = evidence.apply_transform(original, t)
    pixels = [(i % shown.width, i // shown.width) for i, v in enumerate(shown.get_flattened_data()) if v < 100]
    cx = sum(p[0] for p in pixels) / len(pixels) / shown.width
    cy = sum(p[1] for p in pixels) / len(pixels) / shown.height
    x, y, w, h = evidence.to_source([cx - 0.01, cy - 0.01, 0.02, 0.02], t)
    ox, oy = dot[0] / original.width, dot[1] / original.height
    assert x <= ox <= x + w and y <= oy <= y + h, ((x, y, w, h), (ox, oy))
    assert w < 0.05 and h < 0.05  # a small place stays a small place


def test_straightening_values_are_checked() -> None:
    with pytest.raises(evidence.Rejected):
        evidence.check_transform({"straighten": "auto"})  # only the page worker resolves "auto"
    with pytest.raises(evidence.Rejected):
        evidence.check_transform({"straighten": 12})
    with pytest.raises(evidence.Rejected):
        evidence.check_transform({"straighten": "sideways"})
    assert evidence.check_transform({"straighten": 0}) == {"rotate": 0, "crop": None, "enhance": False}  # unchanged
    with pytest.raises(evidence.Rejected):  # a stored angle without the page's shape can't be mapped
        evidence.to_source([0, 0, 1, 1], {"straighten": 3.0})


def _rollout(percent: int | None) -> None:
    with get_sessionmaker()() as db:
        db.execute(text("delete from feature_rollout where key = 'page_straighten'"))
        if percent is not None:
            db.execute(
                text(
                    "insert into feature_rollout (key, percent, reason, updated_by) "
                    "select 'page_straighten', :p, 'Fixture: straightening rollout test', id from app_user limit 1"
                ),
                {"p": percent},
            )
        db.commit()


def test_a_learner_straightens_a_crooked_page_and_markers_see_it_and_the_original(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner = _learner(client)
    attempt = _start(client, learner, published_written["chapter"])
    up = _upload(client, learner, attempt["id"], _png(_tilted(5.0))).json()["pages"][0]
    url = f"/v1/written-attempts/{attempt['id']}/pages/{up['id']}/transform"
    try:
        _rollout(0)  # as in staging and production until it is qualified
        off = client.put(url, headers=learner.headers, json={"straighten": "auto"})
        assert off.status_code == 404 and off.json()["code_reason"] == "FEATURE_NOT_AVAILABLE"
        _rollout(None)  # development's default: on

        done = client.put(url, headers=learner.headers, json={"straighten": "auto"})
        assert done.status_code == 200, done.text
        t = done.json()["transform"]
        assert abs(t["straighten"] + 5.0) <= 0.3 and t["aspect"] and t["rotate"] == 0
        assert done.json()["width"] > up["width"]  # the turned page grew; nothing was cut off

        # Kept while other changes are made, and a trim of the straightened page maps back to the original.
        trimmed = client.put(url, headers=learner.headers, json={**t, "enhance": True, "trim": [0.05, 0.05, 0.9, 0.9]})
        assert trimmed.status_code == 200, trimmed.text
        kept = trimmed.json()["transform"]
        assert kept["straighten"] == t["straighten"] and kept["enhance"] is True
        assert kept["shown_crop"] == [0.05, 0.05, 0.9, 0.9] and kept["crop"] is None  # in the straightened page's terms
        assert trimmed.json()["width"] < done.json()["width"]
        _rollout(0)  # switched off later: keeping the same angle and undoing it are still allowed
        assert client.put(url, headers=learner.headers, json=kept).status_code == 200
        undone = client.put(url, headers=learner.headers, json={**kept, "straighten": 0})
        assert undone.status_code == 200 and undone.json()["transform"]["straighten"] == 0
        _rollout(None)
        final = client.put(url, headers=learner.headers, json={"straighten": "auto"}).json()

        m = _map(client, learner, attempt, {"1:a": {"pages": [up["id"]]}, "1:b": {"unanswered": True}}).json()
        assert _seal(client, learner, attempt["id"], m["manifest_revision"]).status_code == 200
        reviewer = _reviewer(client)
        case = _case_for(client, reviewer, attempt["id"])
        client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)
        detail = f"/v1/studio/written/cases/{case['id']}/pages/{up['id']}/detail"
        as_shown = client.get(detail, headers=reviewer.headers, params={"region": "0.2,0.2,0.3,0.2"})
        original = client.get(detail, headers=reviewer.headers, params={"original": "true"})
        assert as_shown.status_code == 200, as_shown.text
        assert original.status_code == 200
        assert (
            "view=as-shown" in as_shown.headers["x-derivative"] and "view=original" in original.headers["x-derivative"]
        )
        assert Image.open(io.BytesIO(original.content)).size[0] < Image.open(io.BytesIO(original.content)).size[1]
        assert abs(final["transform"]["straighten"] + 5.0) <= 0.3
    finally:
        _rollout(None)
