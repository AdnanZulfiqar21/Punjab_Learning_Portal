"""W03.S2.T1 (SCAN-QUALITY-01): actionable quality checks on uploaded pages.

Each page is checked in the evidence worker for blur, glare, writing cut off at an edge, and a page too small in the
photo. A check is `likely` or `possible`, comes with a retake suggestion, and never rejects the page: only a teacher
decides a page is unreadable (and can ask for a clearer copy). Every image here is a labelled synthetic technical
fixture (printed lines of fixture text drawn with Pillow), not a learner script; the thresholds are provisional until
calibrated on real scans.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from portal_api.modules.written import evidence
from tests.test_written_attempts import _learner, _pdf, _start, _upload


def _page(margin: int = 120, bg: int = 215, size: tuple[int, int] = (1500, 2000)) -> Image.Image:
    im = Image.new("L", size, bg)
    draw = ImageDraw.Draw(im)
    font = ImageFont.load_default(size=36)
    for i, y in enumerate(range(margin, size[1] - margin, 58)):
        draw.text((margin, y), f"Technical fixture writing line {i}, not a learner script", fill=40, font=font)
    return im


def _bytes(im: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    im.convert("RGB" if fmt == "JPEG" else "L").save(buf, format=fmt, **({"quality": 80} if fmt == "JPEG" else {}))
    return buf.getvalue()


def _glare() -> Image.Image:
    im = _page()
    ImageDraw.Draw(im).ellipse((500, 500, 1100, 1000), fill=255)
    return im


def _on_table() -> Image.Image:
    table = Image.new("L", (1700, 2200), 60)
    table.paste(_page(), (100, 100))
    return table


def _far_away() -> Image.Image:
    photo = Image.new("L", (3000, 4000), 50)
    photo.paste(_page().resize((600, 800)), (1200, 1600))
    return photo


@pytest.mark.parametrize(
    ("image", "fmt", "expected"),
    [
        (_page(), "PNG", []),
        (_page(), "JPEG", []),
        (_page(bg=255), "PNG", []),  # a clean white scan is not glare
        (_on_table(), "JPEG", []),  # a dark table around the page is not cut-off writing
        (Image.new("L", (1500, 2000), 215), "PNG", []),  # a blank page has nothing to judge sharpness by
        (_page().filter(ImageFilter.GaussianBlur(3)), "JPEG", [("blur", "likely")]),
        (_page().filter(ImageFilter.GaussianBlur(2)), "PNG", [("blur", "possible")]),
        (_glare(), "PNG", [("glare", "likely")]),
        (_page(margin=0), "PNG", [("cut_off", "likely")]),
        (_page().resize((525, 700)), "PNG", [("small_text", "likely")]),
        (_far_away(), "JPEG", [("small_text", "possible")]),
    ],
    ids=["sharp", "sharp-jpeg", "white-scan", "on-a-table", "blank", "blurry", "slightly-blurry", "glare", "cut-off",
         "small-photo", "page-far-away"],
)  # fmt: skip
def test_each_check_flags_its_own_problem_and_nothing_else(image: Image.Image, fmt: str, expected: list[Any]) -> None:
    page = evidence.inspect(_bytes(image, fmt)).pages[0]
    assert [(f["code"], f["level"]) for f in page.quality] == expected


def test_flags_carry_a_retake_suggestion_and_never_reject() -> None:
    cut = evidence.inspect(_bytes(_page(margin=0)))
    flag = cut.pages[0].quality[0]
    assert flag["sides"] == ["top", "bottom", "left"]  # in the order top, bottom, left, right
    assert cut.warnings == [evidence.quality_message(flag)]
    assert "the top, bottom and left edges" in cut.warnings[0] and "Retake" in cut.warnings[0]
    blurry = evidence.inspect(_bytes(_page().filter(ImageFilter.GaussianBlur(2))))
    assert blurry.pages and "may be slightly blurry" in blurry.warnings[0]  # `possible` asks the learner to check
    # A PDF's pages are each checked; a page drawn by software has nothing to warn about.
    assert all(p.quality == [] for p in evidence.inspect(_pdf(3)).pages)


def test_uploads_return_and_keep_each_pages_flags(client: TestClient, published_written: dict[str, Any]) -> None:
    who = _learner(client)
    attempt = _start(client, who, published_written["chapter"])
    sharp = _upload(client, who, attempt["id"], _bytes(_page(), "JPEG"))
    assert sharp.status_code == 201 and sharp.json()["pages"][0]["quality"] == [] and sharp.json()["warnings"] == []
    glare = _upload(client, who, attempt["id"], _bytes(_glare()))
    assert glare.status_code == 201, glare.text  # a warning never stops an upload
    flags = glare.json()["pages"][0]["quality"]
    assert [(f["code"], f["level"]) for f in flags] == [("glare", "likely")] and "reflecting" in flags[0]["message"]
    assert glare.json()["warnings"] == [flags[0]["message"]]  # older apps still get the plain warning
    again = client.get(f"/v1/written-attempts/{attempt['id']}", headers=who.headers).json()
    assert [p["quality"] for p in again["pages"]] == [[], flags]  # stored with the page, for the learner and reviewers
