"""Bounded validation of uploaded evidence (W03.S3.T2, §20.8).

Checks the file signature (never the extension or the client's content type), size caps, decoded image dimensions
from the header only (no full decode), and for PDFs a page count plus refusal of active or unsafe content. Anything
unsupported or unsafe is a recoverable processing error, never an academic zero. Full sandboxed conversion belongs in
an isolated worker (W03.S1.T3) and is not done in the request.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass

IMAGE_MAX_BYTES = 15 * 1024 * 1024
PDF_MAX_BYTES = 40 * 1024 * 1024
MAX_SIDE_PX = 12_000
MIN_LONG_EDGE_PX = 800  # below this, small writing is unlikely to be legible: warn (never reject on quality alone)
PDF_MAX_PAGES = 10

_PDF_UNSAFE = [rb"/JavaScript", rb"/JS\b", rb"/Launch", rb"/EmbeddedFile", rb"/Encrypt", rb"/RichMedia", rb"/XFA"]


class Rejected(ValueError):
    """The file can't be accepted (unsupported or unsafe). `reason` is shown to the learner."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Checked:
    content_type: str
    width: int | None
    height: int | None
    pages: int
    warnings: list[str]


def sniff(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:5] == b"%PDF-":
        return "application/pdf"
    raise Rejected("Only JPEG, PNG or PDF files can be uploaded.")


def _png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise Rejected("This PNG file is damaged.")
    w, h = struct.unpack(">II", data[16:24])
    return int(w), int(h)


def _jpeg_size(data: bytes) -> tuple[int, int]:
    i = 2
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
        # Start-of-frame markers carry the dimensions.
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if i + 9 > n:
                break
            h, w = struct.unpack(">HH", data[i + 5 : i + 9])
            return int(w), int(h)
        i += 2 + seg_len
    raise Rejected("This JPEG file is damaged or incomplete.")


def check(data: bytes) -> Checked:
    if not data:
        raise Rejected("The file is empty.")
    kind = sniff(data)
    warnings: list[str] = []
    if kind == "application/pdf":
        if len(data) > PDF_MAX_BYTES:
            raise Rejected(f"PDFs can be at most {PDF_MAX_BYTES // (1024 * 1024)} MB.")
        if any(re.search(p, data) for p in _PDF_UNSAFE):
            raise Rejected("This PDF contains active, encrypted or embedded content and can't be accepted.")
        pages = len(re.findall(rb"/Type\s*/Page(?!s)", data))
        if pages == 0:
            raise Rejected("This PDF has no readable pages.")
        if pages > PDF_MAX_PAGES:
            raise Rejected(f"A PDF can have at most {PDF_MAX_PAGES} pages.")
        return Checked(kind, None, None, pages, warnings)
    if len(data) > IMAGE_MAX_BYTES:
        raise Rejected(f"Images can be at most {IMAGE_MAX_BYTES // (1024 * 1024)} MB.")
    w, h = _png_size(data) if kind == "image/png" else _jpeg_size(data)
    if w <= 0 or h <= 0 or w > MAX_SIDE_PX or h > MAX_SIDE_PX:
        raise Rejected(f"Image dimensions must be between 1 and {MAX_SIDE_PX} pixels per side.")
    if max(w, h) < MIN_LONG_EDGE_PX:
        warnings.append("This photo is small; faint or small writing may be hard to read. Consider a clearer photo.")
    return Checked(kind, w, h, 1, warnings)
