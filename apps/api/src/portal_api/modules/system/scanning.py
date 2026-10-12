"""Upload scanning (roadmap P06.S4.T1; UPLOAD-SCAN-01).

Every learner upload (written evidence, rescans, help screenshots) is scanned *before* anything is stored:

* `clamd`: the ClamAV daemon over TCP with the INSTREAM protocol (no extra dependency). Deployed roles must use it;
  the configuration validator refuses to start them with `none`.
* `none`: development/test only. Nothing is scanned; the file still goes through every other check (decoders,
  re-encoding, isolated processing).

A flagged file is refused with a reason (422 `FILE_REFUSED`) and nothing is kept. If the scanner can't be reached the
upload fails closed with a retryable 503 (`SCANNER_UNAVAILABLE`): an unscanned file is never stored in a deployed role.
"""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass

from portal_api.config import get_settings
from portal_api.errors import Unavailable, Unprocessable

CHUNK = 64 * 1024


@dataclass(frozen=True)
class Verdict:
    status: str  # clean | infected | unavailable | not_scanned
    signature: str | None = None


class ScannerUnavailable(Unavailable):
    code = "SCANNER_UNAVAILABLE"
    retry_after = 60


class ClamdScanner:
    def __init__(self, host: str, port: int, timeout: float = 30.0) -> None:
        self.host, self.port, self.timeout = host, port, timeout

    def scan(self, data: bytes) -> Verdict:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as conn:
                conn.sendall(b"zINSTREAM\x00")
                for i in range(0, len(data), CHUNK):
                    part = data[i : i + CHUNK]
                    conn.sendall(struct.pack(">I", len(part)) + part)
                conn.sendall(struct.pack(">I", 0))
                reply = b""
                while not reply.endswith(b"\x00"):
                    more = conn.recv(4096)
                    if not more:
                        break
                    reply += more
        except OSError:
            return Verdict("unavailable")
        text = reply.rstrip(b"\x00").decode("utf-8", "replace").strip()
        if text.endswith(" FOUND"):
            return Verdict("infected", text.removeprefix("stream:").removesuffix("FOUND").strip())
        if text.endswith(" OK"):
            return Verdict("clean")
        return Verdict("unavailable")  # an error reply (e.g. size limit exceeded) is never treated as clean


def scan(data: bytes) -> Verdict:
    s = get_settings()
    if s.upload_scanner == "clamd":
        return ClamdScanner(s.clamd_host, s.clamd_port).scan(data)
    return Verdict("not_scanned")


def require_clean(data: bytes) -> None:
    """Refuse a flagged file; fail closed when the scanner can't answer."""
    verdict = scan(data)
    if verdict.status == "infected":
        raise Unprocessable(
            "This file was refused by the safety scan. Please check your device and upload a fresh copy.",
            code_reason="FILE_REFUSED",
        )
    if verdict.status == "unavailable":
        raise ScannerUnavailable(
            "We can't check uploads right now. Please try this file again in a few minutes.",
            code_reason="SCANNER_UNAVAILABLE",
        )
