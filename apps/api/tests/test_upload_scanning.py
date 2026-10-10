"""P06.S4.T1 (UPLOAD-SCAN-01): every learner upload is scanned before anything is stored. A flagged file is refused
with a reason and nothing is kept; an unreachable scanner fails closed (503, retryable). Deployed roles must use a real
scanner. The clamd client is exercised against a local fake server speaking the INSTREAM protocol. Synthetic files
only (the EICAR string is the industry's harmless test signature, never real malware)."""

from __future__ import annotations

import socket
import struct
import threading
from typing import Any

import pytest
from fastapi.testclient import TestClient

from portal_api.config import ConfigurationError, Settings
from portal_api.modules.system import scanning
from portal_api.modules.written import storage
from tests.test_support_attachments import _attach, _staff, _ticket
from tests.test_written_attempts import _png, _start, _upload


def _fake_clamd(reply: bytes) -> tuple[int, list[bytes]]:
    received: list[bytes] = []
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)

    def serve() -> None:
        conn, _ = server.accept()
        with conn:
            buf = b""
            while not buf.endswith(b"\x00\x00\x00\x00"):  # INSTREAM ends with a zero-length chunk
                part = conn.recv(65536)
                if not part:
                    break
                buf += part
            received.append(buf)
            conn.sendall(reply)
        server.close()

    threading.Thread(target=serve, daemon=True).start()
    return server.getsockname()[1], received


def test_the_clamd_client_speaks_instream() -> None:
    port, received = _fake_clamd(b"stream: Eicar-Test-Signature FOUND\x00")
    verdict = scanning.ClamdScanner("127.0.0.1", port, timeout=5).scan(b"fixture bytes")
    assert verdict == scanning.Verdict("infected", "Eicar-Test-Signature")
    assert received[0].startswith(b"zINSTREAM\x00") and struct.pack(">I", 13) + b"fixture bytes" in received[0]
    port, _ = _fake_clamd(b"stream: OK\x00")
    assert scanning.ClamdScanner("127.0.0.1", port, timeout=5).scan(b"clean").status == "clean"
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    dead_port = closed.getsockname()[1]
    closed.close()
    assert scanning.ClamdScanner("127.0.0.1", dead_port, timeout=1).scan(b"x").status == "unavailable"


def test_deployed_roles_need_a_real_scanner() -> None:
    with pytest.raises(ConfigurationError, match="upload_scanner"):
        Settings(role="production", upload_scanner="none")  # type: ignore[arg-type]


def _flagging(status: str) -> Any:
    return lambda data: scanning.Verdict(status, "Fixture-Signature" if status == "infected" else None)


def test_flagged_or_unscannable_uploads_are_refused_before_storage(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    before = {k for k, _ in storage.get_store().list_objects()}
    learner = _staff(client, [])
    ticket = _ticket(client, learner)
    monkeypatch.setattr(scanning, "scan", _flagging("infected"))
    r = _attach(client, learner, ticket["id"], _png())
    assert r.status_code == 422 and r.json()["code_reason"] == "FILE_REFUSED", r.text
    who = _staff(client, [])
    client.post("/v1/me/trial", headers=who.headers)
    attempt = _start(client, who, published_written["chapter"])
    up = _upload(client, who, attempt["id"], _png())
    assert up.status_code == 422 and up.json()["code_reason"] == "FILE_REFUSED"
    monkeypatch.setattr(scanning, "scan", _flagging("unavailable"))
    down = _attach(client, learner, ticket["id"], _png())
    assert down.status_code == 503 and down.json()["code_reason"] == "SCANNER_UNAVAILABLE"
    assert {k for k, _ in storage.get_store().list_objects()} == before  # nothing was stored
    monkeypatch.undo()
    assert _attach(client, learner, ticket["id"], _png()).status_code == 201  # the development default still works
