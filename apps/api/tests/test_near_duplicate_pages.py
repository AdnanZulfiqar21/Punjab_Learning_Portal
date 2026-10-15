"""W03.S2.T3 (NEAR-DUP-01): the same page uploaded twice with different bytes (re-compressed, resized, a little lighter)
is flagged as possibly the same page, never removed; different pages and blank sheets are not flagged. Synthetic
"writing" drawn from a seed only: no learner work."""

from __future__ import annotations

import io
import random
from typing import Any

from fastapi.testclient import TestClient

from portal_api.modules.written import evidence
from tests.test_written_attempts import _learner, _start, _upload


def _writing(seed: int, w: int = 1200, h: int = 1600) -> Any:
    """A white page with ruled lines and seeded pen strokes standing in for handwriting."""
    from PIL import Image, ImageDraw

    rng = random.Random(seed)  # noqa: S311 - a seeded synthetic drawing, not a secret
    im = Image.new("L", (w, h), 245)
    d = ImageDraw.Draw(im)
    for y in range(120, h - 80, 70):
        d.line([(60, y), (w - 60, y)], fill=200, width=2)
        x = 80 + rng.randrange(0, 60)
        while x < w - 140 and rng.random() > 0.08:
            word = rng.randrange(30, 140)
            for _ in range(rng.randrange(3, 9)):
                x0, y0 = x + rng.randrange(0, word), y - rng.randrange(10, 45)
                d.line([(x0, y0), (x0 + rng.randrange(-20, 20), y0 + rng.randrange(5, 40))], fill=25, width=4)
            x += word + rng.randrange(20, 50)
    return im


def _encode(im: Any, fmt: str = "PNG", **kw: Any) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format=fmt, **kw)
    return buf.getvalue()


def _again(im: Any) -> bytes:
    """The same page photographed or shared again: smaller, a little lighter, saved as a lossy JPEG."""
    from PIL import ImageEnhance

    smaller = im.resize((round(im.width * 0.85), round(im.height * 0.85)))
    return _encode(ImageEnhance.Brightness(smaller).enhance(1.04).convert("RGB"), "JPEG", quality=70)


def _flags(page: dict[str, Any]) -> list[dict[str, Any]]:
    return [q for q in page["quality"] if q["code"] == "near_duplicate"]


def test_fingerprints_tell_the_same_page_from_a_different_one() -> None:
    from PIL import Image

    page = _writing(1)
    a = evidence._fingerprint(page)
    same = evidence._fingerprint(Image.open(io.BytesIO(_again(page))))
    other = evidence._fingerprint(_writing(2))
    assert a is not None and same is not None and other is not None
    assert evidence.near_duplicate(a, same)
    assert not evidence.near_duplicate(a, other)
    assert evidence._fingerprint(Image.new("L", (1200, 1600), 250)) is None  # a blank sheet has nothing to compare
    assert not evidence.near_duplicate(a, None)
    assert evidence._valid_fingerprint("zz" * 1024) is None and evidence._valid_fingerprint(a) == a


def test_the_same_page_twice_is_flagged_and_kept_and_the_flag_survives_a_turn(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner = _learner(client)
    attempt = _start(client, learner, published_written["chapter"])
    page = _writing(11)

    first = _upload(client, learner, attempt["id"], _encode(page)).json()["pages"][0]
    assert _flags(first) == []
    different = _upload(client, learner, attempt["id"], _encode(_writing(12))).json()["pages"][0]
    assert _flags(different) == []  # another page of writing is not the same page

    again = _upload(client, learner, attempt["id"], _again(page))
    assert again.status_code == 201, again.text
    body = again.json()
    assert body["duplicate"] is False  # different bytes: a new page, kept
    [flag] = _flags(body["pages"][0])
    assert flag["like_page_id"] == first["id"] and flag["level"] == "possible"
    assert "looks almost the same as another page" in flag["message"]

    listed = client.get(f"/v1/written-attempts/{attempt['id']}", headers=learner.headers).json()["pages"]
    assert [p["id"] for p in listed] == [first["id"], different["id"], body["pages"][0]["id"]]  # nothing removed

    turned = client.put(
        f"/v1/written-attempts/{attempt['id']}/pages/{body['pages'][0]['id']}/transform",
        headers=learner.headers,
        json={"rotate": 90},
    )
    assert turned.status_code == 200, turned.text
    assert [f["like_page_id"] for f in _flags(turned.json())] == [first["id"]]  # about the upload, so it stays


def test_blank_sheets_are_never_flagged(client: TestClient, published_written: dict[str, Any]) -> None:
    from PIL import Image

    learner = _learner(client)
    attempt = _start(client, learner, published_written["chapter"])
    for shade in (250, 251, 252):
        up = _upload(client, learner, attempt["id"], _encode(Image.new("L", (1200, 1600), shade)))
        assert up.status_code == 201, up.text
        assert _flags(up.json()["pages"][0]) == []
