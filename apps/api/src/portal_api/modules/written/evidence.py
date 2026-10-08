"""Bounded inspection of uploaded evidence in a separate worker process (W03.S1.T3, W03.S3.T2, §20.8; review R01).

The API process never decodes learner files itself. `inspect()` writes the bytes to a private temporary directory and
runs this module as a child process with a wall-clock timeout and, on POSIX hosts, address-space and CPU limits. The
child decodes with maintained parsers (Pillow for JPEG/PNG, PDFium through pypdfium2 for PDF), enforces byte, pixel,
page and size limits, and renders one PNG preview per logical page. Teachers and learners only ever see these
previews; the original stays private and immutable.

A file that can't be decoded, is encrypted, carries document JavaScript or attachments, or exceeds a limit is a
recoverable processing rejection shown to the learner. It is never an academic mark.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

IMAGE_MAX_BYTES = 15 * 1024 * 1024
PDF_MAX_BYTES = 40 * 1024 * 1024
MAX_SIDE_PX = 12_000
MAX_IMAGE_PIXELS = 60_000_000  # decoded pixels per image; a decompression bomb is refused before decoding
MIN_LONG_EDGE_PX = 800  # below this, small writing is unlikely to be legible: warn (never reject on quality alone)
PDF_MAX_PAGES = 10
PDF_MAX_SIDE_PT = 14_400  # 200 inches; PDFium's own limit, and far beyond any paper size
PREVIEW_LONG_EDGE_PX = 2_000
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


def inspect(data: bytes) -> Inspected:
    """Validate and render previews in an isolated child process. Raises Rejected with a learner-facing reason."""
    kind = precheck(data)
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
            LogicalPage(width=int(p["width"]), height=int(p["height"]), preview_png=(work / p["preview"]).read_bytes())
            for p in result["pages"]
        ]
        return Inspected(content_type=kind, pages=pages, warnings=list(result.get("warnings", [])))


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
    warnings_out = []
    if max(upright.size) < MIN_LONG_EDGE_PX:
        warnings_out.append(
            "This photo is small; faint or small writing may be hard to read. Consider a clearer photo."
        )
    return {
        "pages": [{"width": pw, "height": ph, "preview": "page-1.png", "_png": png}],
        "warnings": warnings_out,
    }


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
                png, w, h = _preview(bitmap.to_pil())
            finally:
                page.close()
            pages.append({"width": w, "height": h, "preview": f"page-{i + 1}.png", "_png": png})
        return {"pages": pages, "warnings": []}
    finally:
        doc.close()


def _worker(work: Path, kind: str) -> None:
    _limit_resources()
    data = (work / "input").read_bytes()
    result = _inspect_pdf(data) if kind == "application/pdf" else _inspect_image(data, kind)
    for p in result.get("pages", []):
        (work / p["preview"]).write_bytes(p.pop("_png"))
    (work / "result.json").write_text(json.dumps(result), encoding="utf8")


if __name__ == "__main__":
    _worker(Path(sys.argv[1]), sys.argv[2])
