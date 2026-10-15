"""Bounded inspection of uploaded evidence in a separate worker process (W03.S1.T3, W03.S3.T2, §20.8; review R01).

The API process never decodes learner files itself. `inspect()` writes the bytes to a private temporary directory and
runs this module as a child process with a wall-clock timeout and, on POSIX hosts, address-space and CPU limits. The
child decodes with maintained parsers (Pillow for JPEG/PNG, PDFium through pypdfium2 for PDF), enforces byte, pixel,
page and size limits, and renders one PNG preview per logical page. Teachers and learners only ever see these
previews; the original stays private and immutable.

A file that can't be decoded, is encrypted, carries document JavaScript or attachments, or exceeds a limit is a
recoverable processing rejection shown to the learner. It is never an academic mark.

W03.S1.T3 (TRANSFORMS-01): a learner may turn a page, trim its edges or ask for a clearer-contrast preview before
submitting. These are derived transforms recorded with the page and applied to a fresh render of the untouched
original (`apply_transform`); regions on a transformed page map back to the original with `to_source`.

W03.S2.T1 (SCAN-QUALITY-01): each logical page is also checked for blur, glare, writing cut off at an edge, and a
page too small in the photo. A check is `likely` or `possible` and comes with a retake suggestion; it never
rejects a page. Only a teacher decides a page is unreadable, and can ask for a clearer copy (W04.S3.T2).
"""

from __future__ import annotations

import io
import itertools
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

IMAGE_MAX_BYTES = 15 * 1024 * 1024
PDF_MAX_BYTES = 40 * 1024 * 1024
MAX_SIDE_PX = 12_000
MAX_IMAGE_PIXELS = 60_000_000  # decoded pixels per image; a decompression bomb is refused before decoding
MIN_LONG_EDGE_PX = 800  # below this, small writing is unlikely to be legible: warn (never reject on quality alone)
PDF_MAX_PAGES = 10
PDF_MAX_SIDE_PT = 14_400  # 200 inches; PDFium's own limit, and far beyond any paper size
PREVIEW_LONG_EDGE_PX = 2_000
DETAIL_PAGE_LONG_EDGE_PX = 4_000  # OCT8-06: full-page detail for marking small symbols and labels
DETAIL_REGION_LONG_EDGE_PX = 3_000  # a requested region is rendered up to this size
DETAIL_MAX_PDF_DPI = 600
WORKER_TIMEOUT_S = 30
WORKER_MEMORY_BYTES = 1024 * 1024 * 1024
WORKER_CPU_S = 25


class Rejected(ValueError):
    """The file can't be accepted (unsupported, damaged, unsafe or over a limit). `reason` is shown to the learner."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class LogicalPage:
    width: int
    height: int
    preview_png: bytes
    quality: list[dict[str, Any]] = field(default_factory=list)  # SCAN-QUALITY-01 flags (see `quality_message`)
    transform: dict[str, Any] | None = None  # STRAIGHTEN-01: as applied (the angle found, the page's shape before it)
    fingerprint: str | None = None  # NEAR-DUP-01: a coarse thumbnail for spotting the same page twice (None: blank)


@dataclass(frozen=True)
class Inspected:
    content_type: str
    pages: list[LogicalPage]
    warnings: list[str] = field(default_factory=list)


def sniff(data: bytes) -> str:
    """Cheap intake filter only. A matching signature is never treated as proof that the file is valid."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:5] == b"%PDF-":
        return "application/pdf"
    raise Rejected("Only JPEG, PNG or PDF files can be uploaded.")


def precheck(data: bytes) -> str:
    """Signature and byte limits, before spending a worker on the file."""
    if not data:
        raise Rejected("The file is empty.")
    kind = sniff(data)
    if kind == "application/pdf" and len(data) > PDF_MAX_BYTES:
        raise Rejected(f"PDFs can be at most {PDF_MAX_BYTES // (1024 * 1024)} MB.")
    if kind != "application/pdf" and len(data) > IMAGE_MAX_BYTES:
        raise Rejected(f"Images can be at most {IMAGE_MAX_BYTES // (1024 * 1024)} MB.")
    return kind


class WorkersBusy(RuntimeError):
    """Every evidence worker slot stayed busy for the wait limit: answered as a retryable 503."""


MAX_WORKERS = 4  # concurrent child processes per API process (memory bound), independent of the DB pool
WORKER_QUEUE_WAIT_S = 20
_slots = threading.BoundedSemaphore(MAX_WORKERS)


def inspect(data: bytes) -> Inspected:
    """Validate and render previews in an isolated child process. Raises Rejected with a learner-facing reason."""
    kind = precheck(data)
    if not _slots.acquire(timeout=WORKER_QUEUE_WAIT_S):
        raise WorkersBusy("evidence workers are busy")
    try:
        return _run_worker(data, kind)
    finally:
        _slots.release()


ROTATIONS = (0, 90, 180, 270)  # clockwise degrees
MIN_CROP = 0.3  # a trim keeps at least this share of each side, so a slip can't remove most of a page
STRAIGHTEN_MAX = 10.0  # degrees either way; a page more crooked than this is turned or photographed again


def _check_crop(raw: Any) -> list[float] | None:
    if raw is None:
        return None
    try:
        x, y, w, h = (float(v) for v in raw)
    except (TypeError, ValueError) as e:
        raise Rejected("A trim is four numbers: x, y, width and height.") from e
    if min(x, y) < 0 or x + w > 1.0001 or y + h > 1.0001:
        raise Rejected("A trim must stay inside the page.")
    if w < MIN_CROP or h < MIN_CROP:
        raise Rejected("That trim would remove most of the page. Keep at least a third of each side.")
    crop = [round(x, 4), round(y, 4), round(w, 4), round(h, 4)]
    return None if crop == [0.0, 0.0, 1.0, 1.0] else crop


def check_transform(raw: dict[str, Any] | None, *, allow_auto: bool = False) -> dict[str, Any]:
    """TRANSFORMS-01: a page's transform as stored: rotation, an optional crop of the upright original (x, y, w, h
    fractions) and an optional readability boost. STRAIGHTEN-01 adds an optional small rotation (`straighten`, degrees
    counter-clockwise as shown) with `aspect`, the width/height of the page just before it, which region mapping
    needs. `straighten: "auto"` (with `allow_auto`) asks the page worker to find the angle. Raises Rejected with a
    learner-facing reason."""
    raw = raw or {}
    rotate = int(raw.get("rotate", 0))
    if rotate not in ROTATIONS:
        raise Rejected("A page can only be turned in quarter turns.")
    crop = _check_crop(raw.get("crop"))
    out: dict[str, Any] = {"rotate": rotate, "crop": crop, "enhance": bool(raw.get("enhance", False))}
    straighten = raw.get("straighten") or 0
    if straighten == "auto":
        if not allow_auto:
            raise Rejected("Straightening is an angle in degrees.")
        out["straighten"] = "auto"
        return out
    try:
        angle = round(float(straighten), 1)
    except (TypeError, ValueError) as e:
        raise Rejected("Straightening is an angle in degrees.") from e
    if not math.isfinite(angle) or abs(angle) > STRAIGHTEN_MAX:
        raise Rejected(f"A page can be straightened by at most {STRAIGHTEN_MAX:g} degrees either way.")
    if angle:
        aspect = raw.get("aspect")
        if aspect is not None:
            try:
                aspect = float(aspect)
            except (TypeError, ValueError):
                aspect = None
        if aspect is not None and (not math.isfinite(aspect) or not 0.05 <= aspect <= 20):
            aspect = None
        out["straighten"] = angle
        if aspect is not None:
            out["aspect"] = round(aspect, 6)
        shown_crop = _check_crop(raw.get("shown_crop"))  # a trim of the straightened page, in its own coordinates
        if shown_crop is not None:
            out["shown_crop"] = shown_crop
    return out


def _unstraighten(region: tuple[float, float, float, float], angle: float, aspect: float) -> list[float]:
    """STRAIGHTEN-01: a region of the straightened page (fractions) as the smallest region of the page before
    straightening that contains it. PIL's rotate(angle) turns counter-clockwise about the centre and, with expand,
    grows the canvas to (w|cos| + h|sin|, w|sin| + h|cos|); this is its inverse, in units where that page is
    aspect x 1."""
    theta = math.radians(angle)
    c, s_ = math.cos(theta), math.sin(theta)
    w0, h0 = aspect, 1.0
    shown_w, shown_h = w0 * abs(c) + h0 * abs(s_), w0 * abs(s_) + h0 * abs(c)
    x, y, w, h = region
    xs, ys = [], []
    for u, v in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        px, py = u * shown_w - shown_w / 2, v * shown_h - shown_h / 2
        ox, oy = c * px - s_ * py, s_ * px + c * py  # undo the turn
        xs.append((ox + w0 / 2) / w0)
        ys.append((oy + h0 / 2) / h0)
    left, top = max(0.0, min(xs)), max(0.0, min(ys))
    right, bottom = min(1.0, max(xs)), min(1.0, max(ys))
    return [left, top, max(0.0, right - left), max(0.0, bottom - top)]


def estimate_skew(image: Any) -> float:
    """STRAIGHTEN-01: the small turn (degrees, counter-clockwise as PIL's rotate takes it) that makes written lines
    level: the angle whose row profile of ink is sharpest (the projection-profile method), tried every half degree
    within STRAIGHTEN_MAX and then refined to a tenth. 0.0 when there is too little ink to tell or the page is level."""
    from PIL import Image, ImageOps

    grey = ImageOps.grayscale(image)
    scale = min(1.0, 700 / max(grey.size))
    if scale < 1.0:
        size = (max(1, round(grey.width * scale)), max(1, round(grey.height * scale)))
        grey = grey.resize(size, Image.Resampling.BOX)
    grey = ImageOps.autocontrast(grey, cutoff=1)
    ink = grey.point(lambda v: 255 if v < 128 else 0)
    if sum(ink.histogram()[255:]) < 0.002 * ink.width * ink.height:
        return 0.0

    def sharpness(angle: float) -> float:
        turned = ink.rotate(angle, resample=Image.Resampling.NEAREST, expand=True, fillcolor=0)
        column = turned.resize((1, turned.height), Image.Resampling.BOX)
        rows = [float(cast(float, v)) for v in column.get_flattened_data()]  # one band: a number per row
        return float(sum((b - a) ** 2 for a, b in itertools.pairwise(rows)))

    limit = int(STRAIGHTEN_MAX * 2)
    coarse = max((sharpness(a / 2), a / 2) for a in range(-limit, limit + 1))[1]
    fine = max((sharpness(coarse + d / 10), coarse + d / 10) for d in range(-5, 6))[1]
    angle = round(max(-STRAIGHTEN_MAX, min(STRAIGHTEN_MAX, fine)), 1)
    return angle if abs(angle) >= 0.3 else 0.0


def _straighten(image: Any, angle: float) -> Any:
    """Turn by a small angle with nearest-neighbour sampling, so every pixel shown is a pixel of the original (nothing
    is blended lighter); the corners revealed are paper white, and nothing is cut off (expand)."""
    from PIL import Image

    if image.mode not in ("L", "RGB"):
        image = image.convert("L" if image.mode in ("1", "LA", "I", "I;16") else "RGB")
    white: Any = 255 if image.mode == "L" else (255, 255, 255)
    return image.rotate(angle, resample=Image.Resampling.NEAREST, expand=True, fillcolor=white)


def to_source(region: list[float] | tuple[float, ...], transform: dict[str, Any] | None) -> list[float]:
    """Map a region of the transformed page (x, y, w, h fractions) to the same region of the upright original."""
    x, y, w, h = (float(v) for v in region)
    t = check_transform(transform)
    if t.get("straighten"):
        if "aspect" not in t:
            raise Rejected("This page's straightening can't be mapped; straighten it again.")
        if t.get("shown_crop"):  # the trim made on the straightened page
            sx, sy, sw, sh = t["shown_crop"]
            x, y, w, h = sx + x * sw, sy + y * sh, w * sw, h * sh
        x, y, w, h = _unstraighten((x, y, w, h), float(t["straighten"]), float(t["aspect"]))
    rotate = t["rotate"]
    if rotate == 90:  # undo a clockwise quarter turn
        x, y, w, h = y, 1 - x - w, h, w
    elif rotate == 180:
        x, y = 1 - x - w, 1 - y - h
    elif rotate == 270:
        x, y, w, h = 1 - y - h, x, h, w
    cx, cy, cw, ch = t["crop"] or (0.0, 0.0, 1.0, 1.0)
    return [cx + x * cw, cy + y * ch, w * cw, h * ch]


def _cut(image: Any, region: list[float]) -> Any:
    x, y, w, h = region
    return image.crop(
        (
            int(x * image.width),
            int(y * image.height),
            max(int((x + w) * image.width), int(x * image.width) + 1),
            max(int((y + h) * image.height), int(y * image.height) + 1),
        )
    )


def apply_transform(image: Any, transform: dict[str, Any] | None, *, crop: bool = True) -> Any:
    """Crop (in the upright original), turn without resampling, then, if asked, stretch the contrast. Every step is
    lossless or monotonic: nothing that was darker than the paper becomes paper, so faint ink, pencil, small marks and
    edges stay. `crop=False` when the region was already cut out of the original (detail renders)."""
    from PIL import Image, ImageOps

    t = check_transform(transform)
    out = image
    if crop and t["crop"]:
        out = _cut(out, t["crop"])
    turn = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180, 270: Image.Transpose.ROTATE_90}
    if t["rotate"]:
        out = out.transpose(turn[t["rotate"]])
    if t.get("straighten"):
        out = _straighten(out, float(t["straighten"]))
        if crop and t.get("shown_crop"):
            out = _cut(out, t["shown_crop"])
    if t["enhance"]:
        out = ImageOps.autocontrast(out.convert("L" if out.mode in ("1", "L", "LA", "I", "I;16") else "RGB"), cutoff=0)
    return out


def render_page(data: bytes, kind: str, page_index: int, transform: dict[str, Any] | None) -> LogicalPage:
    """TRANSFORMS-01: a fresh preview (and quality checks) of one logical page with its transform, rendered from the
    untouched original in the same isolated, bounded worker. STRAIGHTEN-01: the worker finds the angle for
    `straighten: "auto"`; the page's `transform` reports what was applied."""
    spec = {"page_index": page_index, "transform": check_transform(transform, allow_auto=True)}
    if not _slots.acquire(timeout=WORKER_QUEUE_WAIT_S):
        raise WorkersBusy("evidence workers are busy")
    try:
        with tempfile.TemporaryDirectory(prefix="portal-page-") as tmp:
            work = Path(tmp)
            (work / "input").write_bytes(data)
            (work / "page.json").write_text(json.dumps(spec), encoding="utf8")
            env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP")}
            try:
                proc = subprocess.run(  # noqa: S603 - fixed interpreter and module, no shell
                    [sys.executable, "-I", "-m", "portal_api.modules.written.evidence", str(work), kind, "page"],
                    capture_output=True,
                    timeout=WORKER_TIMEOUT_S,
                    env=env,
                    check=False,
                )
            except subprocess.TimeoutExpired as e:
                raise Rejected("This page took too long to render. Try again.") from e
            out = work / "result.json"
            if proc.returncode != 0 or not out.is_file():
                raise Rejected("This page couldn't be rendered. Try again.")
            result = json.loads(out.read_text(encoding="utf8"))
            if "rejected" in result:
                raise Rejected(str(result["rejected"]))
            return LogicalPage(
                width=int(result["width"]),
                height=int(result["height"]),
                preview_png=(work / "page.png").read_bytes(),
                quality=[f for f in result.get("quality", []) if f.get("code") in QUALITY_TEXT],
                transform=check_transform(result["transform"]) if "transform" in result else None,
            )
    finally:
        _slots.release()


@dataclass(frozen=True)
class Detail:
    png: bytes
    width: int
    height: int
    scale: float  # output pixels per original pixel (images) or per PDF point (PDF)


def render_detail(
    data: bytes,
    kind: str,
    page_index: int,
    region: tuple[float, float, float, float] | None,
    transform: dict[str, Any] | None = None,
) -> Detail:
    """A higher-detail PNG of one logical page (or a region of it, as fractions x, y, w, h of the upright page),
    rendered from the retained original in the same isolated, bounded worker. The original is never served."""
    if region is not None:
        x, y, w, h = region
        if not (
            0 <= x < 1 and 0 <= y < 1 and 0.02 <= w <= 1 and 0.02 <= h <= 1 and x + w <= 1.0001 and y + h <= 1.0001
        ):
            raise Rejected("That region isn't inside the page.")
    if not _slots.acquire(timeout=WORKER_QUEUE_WAIT_S):
        raise WorkersBusy("evidence workers are busy")
    try:
        with tempfile.TemporaryDirectory(prefix="portal-detail-") as tmp:
            work = Path(tmp)
            (work / "input").write_bytes(data)
            spec = {
                "page_index": page_index,
                "region": list(region) if region else None,
                "transform": check_transform(transform) if transform else None,
            }
            (work / "detail.json").write_text(json.dumps(spec), encoding="utf8")
            env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP")}
            try:
                proc = subprocess.run(  # noqa: S603 - fixed interpreter and module, no shell
                    [sys.executable, "-I", "-m", "portal_api.modules.written.evidence", str(work), kind, "detail"],
                    capture_output=True,
                    timeout=WORKER_TIMEOUT_S,
                    env=env,
                    check=False,
                )
            except subprocess.TimeoutExpired as e:
                raise Rejected("This page took too long to render in detail.") from e
            out = work / "result.json"
            if proc.returncode != 0 or not out.is_file():
                raise Rejected("This page couldn't be rendered in detail.")
            result = json.loads(out.read_text(encoding="utf8"))
            if "rejected" in result:
                raise Rejected(str(result["rejected"]))
            return Detail(
                png=(work / "detail.png").read_bytes(),
                width=int(result["width"]),
                height=int(result["height"]),
                scale=float(result["scale"]),
            )
    finally:
        _slots.release()


def _run_worker(data: bytes, kind: str) -> Inspected:
    with tempfile.TemporaryDirectory(prefix="portal-evidence-") as tmp:
        work = Path(tmp)
        (work / "input").write_bytes(data)
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP")}
        try:
            proc = subprocess.run(  # noqa: S603 - fixed interpreter and module, no shell, no learner-controlled args
                [sys.executable, "-I", "-m", "portal_api.modules.written.evidence", str(work), kind],
                capture_output=True,
                timeout=WORKER_TIMEOUT_S,
                env=env,  # minimal environment; -I ignores PYTHON* variables and the user site
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise Rejected("This file took too long to check. Try a smaller photo or a simpler PDF.") from e
        result_path = work / "result.json"
        if proc.returncode != 0 or not result_path.is_file():
            raise Rejected("This file couldn't be processed. Try exporting it again or uploading a photo instead.")
        result = json.loads(result_path.read_text(encoding="utf8"))
        if "rejected" in result:
            raise Rejected(str(result["rejected"]))
        pages = [
            LogicalPage(
                width=int(p["width"]),
                height=int(p["height"]),
                preview_png=(work / p["preview"]).read_bytes(),
                quality=[f for f in p.get("quality", []) if f.get("code") in QUALITY_TEXT],
                fingerprint=_valid_fingerprint(p.get("fingerprint")),
            )
            for p in result["pages"]
        ]
        many = len(pages) > 1
        warnings = [
            f"Page {i}: {quality_message(f)}" if many else quality_message(f)
            for i, lp in enumerate(pages, start=1)
            for f in lp.quality
        ]
        return Inspected(content_type=kind, pages=pages, warnings=warnings)


# ---------------------------------------------------------------- worker side (runs in the child process only)
def _limit_resources() -> None:
    try:
        import resource  # POSIX only; deployed roles run on Linux
    except ImportError:  # Windows development hosts: the timeout and the decoder limits still apply
        return
    setrlimit = getattr(resource, "setrlimit")  # noqa: B009 - absent from the Windows stubs mypy may check against
    setrlimit(getattr(resource, "RLIMIT_AS"), (WORKER_MEMORY_BYTES, WORKER_MEMORY_BYTES))  # noqa: B009
    setrlimit(getattr(resource, "RLIMIT_CPU"), (WORKER_CPU_S, WORKER_CPU_S))  # noqa: B009


def _preview(image: object) -> tuple[bytes, int, int]:
    from PIL import Image

    assert isinstance(image, Image.Image)
    im = image.convert("L" if image.mode in ("1", "L", "LA", "I", "I;16") else "RGB")
    im.thumbnail((PREVIEW_LONG_EDGE_PX, PREVIEW_LONG_EDGE_PX), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG")  # a fresh encode: no metadata, no embedded profiles or text chunks
    return buf.getvalue(), im.width, im.height


def _inspect_image(data: bytes, kind: str) -> dict[str, Any]:
    import warnings

    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    warnings.simplefilter("error", Image.DecompressionBombWarning)
    try:
        with Image.open(io.BytesIO(data), formats=["JPEG"] if kind == "image/jpeg" else ["PNG"]) as im:
            w, h = im.size
            if w <= 0 or h <= 0 or w > MAX_SIDE_PX or h > MAX_SIDE_PX:
                return {"rejected": f"Image dimensions must be between 1 and {MAX_SIDE_PX} pixels per side."}
            if getattr(im, "n_frames", 1) > 1:
                return {"rejected": "Animated images can't be uploaded. Use a single photo per page."}
            im.load()  # full decode: truncated or corrupt data fails here, not later in front of a teacher
            upright = ImageOps.exif_transpose(im)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return {"rejected": "This image has too many pixels to process. Use a normal phone photo."}
    except (OSError, SyntaxError, ValueError):
        return {"rejected": "This image is damaged or incomplete. Take or export the photo again."}
    png, pw, ph = _preview(upright)
    quality = _quality(upright, photo=True)
    page = {"width": pw, "height": ph, "preview": "page-1.png", "_png": png, "quality": quality}
    return {"pages": [{**page, "fingerprint": _fingerprint(upright)}]}


def _inspect_pdf(data: bytes) -> dict[str, Any]:
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    try:
        doc = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as e:
        if "password" in str(e).lower():
            return {"rejected": "This PDF is password-protected. Export it again without a password."}
        return {"rejected": "This PDF is damaged or isn't a real PDF. Export it again or upload photos instead."}
    try:
        n = len(doc)
        if n == 0:
            return {"rejected": "This PDF has no pages."}
        if n > PDF_MAX_PAGES:
            return {"rejected": f"A PDF can have at most {PDF_MAX_PAGES} pages."}
        if raw.FPDFDoc_GetJavaScriptActionCount(doc.raw) > 0 or raw.FPDFDoc_GetAttachmentCount(doc.raw) > 0:
            return {"rejected": "This PDF contains scripts or attached files and can't be accepted."}
        pages = []
        for i in range(n):
            page = doc[i]
            try:
                w_pt, h_pt = page.get_size()
                if w_pt <= 0 or h_pt <= 0 or max(w_pt, h_pt) > PDF_MAX_SIDE_PT:
                    return {"rejected": f"Page {i + 1} of this PDF has an unusable size."}
                scale = min(PREVIEW_LONG_EDGE_PX / max(w_pt, h_pt), 300 / 72)
                bitmap = page.render(scale=scale, may_draw_forms=False)
                rendered = bitmap.to_pil()
                png, w, h = _preview(rendered)
                quality = _quality(rendered, photo=False)  # a PDF page's size is ours to choose: no small-page check
                fingerprint = _fingerprint(rendered)
            finally:
                page.close()
            pages.append(
                {
                    "width": w,
                    "height": h,
                    "preview": f"page-{i + 1}.png",
                    "_png": png,
                    "quality": quality,
                    "fingerprint": fingerprint,
                }
            )
        return {"pages": pages}
    finally:
        doc.close()


# ------------------------------------------------------------------ quality checks (W03.S2.T1, SCAN-QUALITY-01)
# Measured on a grey working copy (long edge QUALITY_WORK_PX). These are provisional engineering thresholds set on
# labelled synthetic pages; they need calibrating on real learner scans. A check only ever *warns*: whether a page
# is unreadable is decided by a teacher, who can ask for a rescan (W04.S3.T2).
QUALITY_WORK_PX = 1000
CONTENT_MIN_STDDEV = 6.0  # a near-blank page has no edges to judge sharpness by
BLUR_LIKELY, BLUR_POSSIBLE = 60, 100  # strongest-edge response (99.5th percentile of |Laplacian|, denoised)
GLARE_LIKELY, GLARE_POSSIBLE = 0.03, 0.01  # share of the page blown out to near-white
GLARE_SKIP_MEDIAN = 240  # a scan whose paper is already pure white has no glare to find
EDGE_BAND = 0.03  # each border band is 3 % of the side
EDGE_PAPER_SHARE = 0.6  # the paper reaches the edge (not a background around the page)
CUT_LIKELY, CUT_POSSIBLE = 0.01, 0.003  # share of ink pixels in a band where the paper reaches the edge
SMALL_LIKELY_PX, SMALL_POSSIBLE_PX = MIN_LONG_EDGE_PX, 1_100  # the page's own long edge in the photo


def _percentile(hist: list[int], share: float) -> int:
    total, acc = sum(hist), 0
    for value, n in enumerate(hist):
        acc += n
        if acc >= total * share:
            return value
    return len(hist) - 1


def _quality(image: Any, *, photo: bool) -> list[dict[str, Any]]:
    """Blur, glare, cut-off edges and a page too small in the photo, each `likely` or `possible`."""
    from PIL import Image, ImageChops, ImageFilter, ImageStat

    def shrink(im: Any) -> tuple[Any, float]:
        scale = min(1.0, QUALITY_WORK_PX / max(im.size))
        size = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
        return im.resize(size, Image.Resampling.BOX), scale

    grey = image.convert("L")
    work, scale = shrink(grey)  # the whole frame, for the page's extent and its edges
    hist = work.histogram()
    median = _percentile(hist, 0.5)
    flags: list[dict[str, Any]] = []

    def level(value: float, likely: float, possible: float, *, below: bool) -> str | None:
        if below:
            return "likely" if value < likely else "possible" if value < possible else None
        return "likely" if value >= likely else "possible" if value >= possible else None

    # The page itself: the bright paper region (a dark table around it is not part of it).
    paper = max(90, int(median * 0.75))
    box = work.point(lambda v: 255 if v >= paper else 0).getbbox()
    if photo:  # with no bright paper found, the whole photo is judged
        page_px = (max(box[2] - box[0], box[3] - box[1]) if box else max(work.size)) / scale
        if lv := level(page_px, SMALL_LIKELY_PX, SMALL_POSSIBLE_PX, below=True):
            flags.append({"code": "small_text", "level": lv})
    # Sharpness and glare are judged on the page alone, at its own working size.
    region = grey.crop(tuple(round(v / scale) for v in box)) if box else grey
    page_work, _ = shrink(region)
    page_hist = page_work.histogram()
    page_median = _percentile(page_hist, 0.5)

    if ImageStat.Stat(page_work).stddev[0] >= CONTENT_MIN_STDDEV:
        quiet = page_work.filter(ImageFilter.MedianFilter(3))
        lap = (0, 1, 0, 1, -4, 1, 0, 1, 0)
        edges = ImageChops.lighter(
            quiet.filter(ImageFilter.Kernel((3, 3), lap, scale=1, offset=0)),
            quiet.filter(ImageFilter.Kernel((3, 3), tuple(-v for v in lap), scale=1, offset=0)),
        )
        if lv := level(_percentile(edges.histogram(), 0.995), BLUR_LIKELY, BLUR_POSSIBLE, below=True):
            flags.append({"code": "blur", "level": lv})

    glare = sum(page_hist[250:]) / sum(page_hist)
    if page_median < GLARE_SKIP_MEDIAN and (lv := level(glare, GLARE_LIKELY, GLARE_POSSIBLE, below=False)):
        flags.append({"code": "glare", "level": lv})

    ink = min(100, median // 2)
    w, h = work.size
    bw, bh = max(2, round(w * EDGE_BAND)), max(2, round(h * EDGE_BAND))
    sides: dict[str, str] = {}
    for side, crop in {
        "top": (0, 0, w, bh),
        "bottom": (0, h - bh, w, h),
        "left": (0, 0, bw, h),
        "right": (w - bw, 0, w, h),
    }.items():
        band = work.crop(crop).histogram()
        n = sum(band)
        reaches_edge = sum(band[paper:]) / n >= EDGE_PAPER_SHARE
        if reaches_edge and (lv := level(sum(band[:ink]) / n, CUT_LIKELY, CUT_POSSIBLE, below=False)):
            sides[side] = lv
    if sides:
        flags.append(
            {"code": "cut_off", "level": "likely" if "likely" in sides.values() else "possible", "sides": list(sides)}
        )
    return flags


# What the learner is told: each flag says what may be wrong and how to retake the page. `possible` is worded as a
# prompt to check the preview, never as a verdict.
QUALITY_TEXT: dict[str, dict[str, str]] = {
    "blur": {
        "likely": "This page looks blurry. Retake the photo holding the phone steady, with the page in focus.",
        "possible": "This page may be slightly blurry. If the writing isn't sharp in the preview, retake it.",
    },
    "glare": {
        "likely": "Light is reflecting off part of this page and may hide writing. Retake it away from bright light.",
        "possible": "There may be a bright reflection on this page. Check the preview; retake it if writing is hidden.",
    },
    "cut_off": {
        "likely": "Writing seems to run off the {sides} edge. Retake it with the whole page and some margin in view.",
        "possible": "Writing may run off the {sides} edge. Check the preview and retake it if anything is missing.",
    },
    "near_duplicate": {
        "possible": "This page looks almost the same as another page you uploaded. If it's the same page twice, "
        "choose just one of them for your answers; if they're different pages, ignore this.",
    },
    "small_text": {
        "likely": "The page is small in this photo, so the writing may be too small to read. Move closer, retake it.",
        "possible": "The page is fairly small in this photo. Check the writing is readable in the preview.",
    },
}


# ------------------------------------------------------- the same page twice (W03.S2.T3, NEAR-DUP-01)
# An exact copy of a file is already recognised by its hash. A page photographed or exported twice (re-compressed,
# resized, lighter or darker) has different bytes, so each page also gets a coarse fingerprint: its 32 x 32 grey
# thumbnail. Two fingerprints are compared after normalising brightness and contrast (each scaled to mean 0, spread 1);
# a mean difference of at most NEAR_DUP_MAX_DIFF flags the pages as possibly the same page. Only flagged, never
# removed: the learner decides. Blank pages get no fingerprint (several blank sheets are normal). Measured on synthetic
# pages only (the same page re-encoded, resized, lightened, darkened or with more contrast: at most 0.26; different
# pages: at least 0.74), so the threshold is provisional, like the others here, until real scans (B10).
FINGERPRINT_SIDE = 32
NEAR_DUP_MAX_DIFF = 0.45  # mean absolute difference of the normalised thumbnails


def _fingerprint(image: Any) -> str | None:
    from PIL import Image, ImageStat

    work = image.convert("L")
    work.thumbnail((QUALITY_WORK_PX, QUALITY_WORK_PX), Image.Resampling.BOX)
    if ImageStat.Stat(work).stddev[0] < CONTENT_MIN_STDDEV:
        return None  # a near-blank page: nothing to tell it apart by
    thumb: bytes = work.resize((FINGERPRINT_SIDE, FINGERPRINT_SIDE), Image.Resampling.BOX).tobytes()
    return thumb.hex()


def _valid_fingerprint(raw: object) -> str | None:
    if not isinstance(raw, str) or len(raw) != FINGERPRINT_SIDE * FINGERPRINT_SIDE * 2:
        return None
    try:
        bytes.fromhex(raw)
    except ValueError:
        return None
    return raw


def _normalised(fingerprint: str) -> list[float]:
    values = list(bytes.fromhex(fingerprint))
    mean = sum(values) / len(values)
    spread = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5 or 1.0
    return [(v - mean) / spread for v in values]


def near_duplicate(a: str | None, b: str | None) -> bool:
    """NEAR-DUP-01: the two pages are probably the same page (both must have content)."""
    if a is None or b is None or len(a) != len(b):
        return False
    x, y = _normalised(a), _normalised(b)
    return sum(abs(i - j) for i, j in zip(x, y, strict=True)) / len(x) <= NEAR_DUP_MAX_DIFF


def quality_message(flag: dict[str, Any]) -> str:
    text = QUALITY_TEXT[flag["code"]][flag["level"]]
    sides = list(flag.get("sides", []))
    if len(sides) > 1:
        return text.replace("{sides} edge", f"{', '.join(sides[:-1])} and {sides[-1]} edges")
    return text.replace("{sides}", sides[0] if sides else "page")


def _detail_worker(work: Path, kind: str) -> None:
    import warnings

    from PIL import Image, ImageOps

    spec = json.loads((work / "detail.json").read_text(encoding="utf8"))
    transform = spec.get("transform")
    region = spec["region"]
    limit = DETAIL_REGION_LONG_EDGE_PX if region else DETAIL_PAGE_LONG_EDGE_PX
    if transform and (region or transform.get("crop")):  # TRANSFORMS-01: the same place on the untouched original
        region = to_source(region or [0.0, 0.0, 1.0, 1.0], transform)
    data = (work / "input").read_bytes()
    if kind == "application/pdf":
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(data)
        try:
            idx = int(spec["page_index"]) - 1
            if not 0 <= idx < len(doc):
                result: dict[str, Any] = {"rejected": "That page doesn't exist in this file."}
            else:
                page = doc[idx]
                try:
                    w_pt, h_pt = page.get_size()
                    rw, rh = (region[2] * w_pt, region[3] * h_pt) if region else (w_pt, h_pt)
                    scale = min(limit / max(rw, rh), DETAIL_MAX_PDF_DPI / 72)
                    crop = (0.0, 0.0, 0.0, 0.0)
                    if region:  # pypdfium2 crop: points removed from left, bottom, right, top
                        x, y, w, h = region
                        crop = (x * w_pt, (1 - y - h) * h_pt, (1 - x - w) * w_pt, y * h_pt)
                    image = page.render(scale=scale, crop=crop, may_draw_forms=False).to_pil()
                finally:
                    page.close()
                if transform:
                    image = apply_transform(image, transform, crop=False)
                image.convert("RGB").save(work / "detail.png", format="PNG")
                result = {"width": image.width, "height": image.height, "scale": scale}
        finally:
            doc.close()
    else:
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data), formats=["JPEG"] if kind == "image/jpeg" else ["PNG"]) as im:
            im.load()
            upright = ImageOps.exif_transpose(im)
        if region:
            x, y, w, h = region
            box = (
                int(x * upright.width),
                int(y * upright.height),
                max(int((x + w) * upright.width), int(x * upright.width) + 1),
                max(int((y + h) * upright.height), int(y * upright.height) + 1),
            )
            upright = upright.crop(box)
        scale = min(1.0, limit / max(upright.size))  # never enlarge beyond the photo's own pixels
        if scale < 1.0:
            upright = upright.resize(
                (max(1, round(upright.width * scale)), max(1, round(upright.height * scale))), Image.Resampling.LANCZOS
            )
        if transform:
            upright = apply_transform(upright, transform, crop=False)
        out = upright.convert("L" if upright.mode in ("1", "L", "LA", "I", "I;16") else "RGB")
        out.save(work / "detail.png", format="PNG")
        result = {"width": out.width, "height": out.height, "scale": scale}
    (work / "result.json").write_text(json.dumps(result), encoding="utf8")


def _page_worker(work: Path, kind: str) -> None:
    """TRANSFORMS-01: re-render one logical page from the original with its transform: preview and quality checks."""
    import warnings

    from PIL import Image, ImageOps

    spec = json.loads((work / "page.json").read_text(encoding="utf8"))
    data = (work / "input").read_bytes()
    if kind == "application/pdf":
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(data)
        try:
            idx = int(spec["page_index"]) - 1
            if not 0 <= idx < len(doc):
                (work / "result.json").write_text(json.dumps({"rejected": "That page doesn't exist."}), encoding="utf8")
                return
            page = doc[idx]
            try:
                w_pt, h_pt = page.get_size()
                image = page.render(scale=min(PREVIEW_LONG_EDGE_PX / max(w_pt, h_pt), 300 / 72), may_draw_forms=False)
                upright = image.to_pil()
            finally:
                page.close()
        finally:
            doc.close()
    else:
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data), formats=["JPEG"] if kind == "image/jpeg" else ["PNG"]) as im:
            im.load()
            upright = ImageOps.exif_transpose(im)
    asked = spec["transform"]
    level = apply_transform(upright, {**asked, "straighten": 0, "enhance": False})  # cropped and turned
    angle = estimate_skew(level) if asked.get("straighten") == "auto" else float(asked.get("straighten") or 0)
    applied = {k: v for k, v in asked.items() if k not in ("straighten", "aspect", "shown_crop")}
    if angle:
        applied.update(straighten=angle, aspect=level.width / level.height)
        if asked.get("straighten") != "auto" and asked.get("shown_crop"):
            applied["shown_crop"] = asked["shown_crop"]
    shown = apply_transform(upright, applied)
    png, w, h = _preview(shown)
    (work / "page.png").write_bytes(png)
    quality = _quality(shown, photo=kind != "application/pdf")
    result = {"width": w, "height": h, "quality": quality, "transform": applied}
    (work / "result.json").write_text(json.dumps(result), encoding="utf8")


def _worker(work: Path, kind: str) -> None:
    _limit_resources()
    data = (work / "input").read_bytes()
    result = _inspect_pdf(data) if kind == "application/pdf" else _inspect_image(data, kind)
    for p in result.get("pages", []):
        (work / p["preview"]).write_bytes(p.pop("_png"))
    (work / "result.json").write_text(json.dumps(result), encoding="utf8")


if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[3] == "detail":
        _limit_resources()
        _detail_worker(Path(sys.argv[1]), sys.argv[2])
    elif len(sys.argv) > 3 and sys.argv[3] == "page":
        _limit_resources()
        _page_worker(Path(sys.argv[1]), sys.argv[2])
    else:
        _worker(Path(sys.argv[1]), sys.argv[2])
