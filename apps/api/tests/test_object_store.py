"""S3-compatible evidence and asset storage (P03.S1.T2).

The signature is checked against the published AWS Signature Version 4 example. Behaviour is checked against a local
stand-in that speaks the same path-style requests, so the suite does not need the compose emulator running.
"""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from portal_api.config import get_settings
from portal_api.modules.content import assets
from portal_api.modules.written import storage
from portal_api.object_store import health, signed_headers


def test_the_signature_matches_the_published_aws_example() -> None:
    headers = signed_headers(
        method="GET",
        host="examplebucket.s3.amazonaws.com",
        path="/test.txt",
        query={},
        body=b"",
        access_key="AKIAIOSFODNN7EXAMPLE",  # pragma: allowlist secret
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # pragma: allowlist secret
        region="us-east-1",
        now=datetime(2013, 5, 24, tzinfo=UTC),
        extra={"range": "bytes=0-9"},
    )
    assert headers["Authorization"].endswith(
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )


class _Store(BaseHTTPRequestHandler):
    objects: ClassVar[dict[tuple[str, str], bytes]] = {}
    buckets: ClassVar[set[str]] = set()

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _parts(self) -> tuple[str, str]:
        path = self.path.split("?", 1)[0]
        bits = [b for b in path.split("/") if b]
        return bits[0], "/".join(bits[1:])

    def do_PUT(self) -> None:
        bucket, key = self._parts()
        if not key:
            self.buckets.add(bucket)
            self.send_response(200)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length)
        if self.headers.get("If-None-Match") == "*" and (bucket, key) in self.objects:
            self.send_response(412)
            self.end_headers()
            return
        self.objects[(bucket, key)] = data
        self.send_response(200)
        self.end_headers()

    def do_GET(self) -> None:
        bucket, key = self._parts()
        if not key:
            prefix = self.path.split("prefix=", 1)[1].split("&", 1)[0].replace("%2F", "/")
            rows = []
            for (name_bucket, name), data in sorted(self.objects.items()):
                if name_bucket == bucket and name.startswith(prefix):
                    rows.append(
                        f"<Contents><Key>{name}</Key><LastModified>2026-10-15T12:00:00.000Z</LastModified>"
                        f"<Size>{len(data)}</Size></Contents>"
                    )
            body = (
                '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                + "".join(rows)
                + "<IsTruncated>false</IsTruncated></ListBucketResult>"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        data = self.objects.get((bucket, key))
        if data is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self) -> None:
        bucket, key = self._parts()
        if not key:
            self.send_response(200 if bucket in self.buckets else 404)
            self.end_headers()
            return
        data = self.objects.get((bucket, key))
        if data is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()

    def do_DELETE(self) -> None:
        self.objects.pop(self._parts(), None)
        self.send_response(204)
        self.end_headers()


@pytest.fixture
def endpoint() -> str:
    _Store.objects = {}
    _Store.buckets = set()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()


def _use(monkeypatch: pytest.MonkeyPatch, endpoint: str) -> None:
    monkeypatch.setenv("PORTAL_EVIDENCE_STORE", "s3")
    monkeypatch.setenv("PORTAL_EVIDENCE_S3_ENDPOINT", endpoint)
    monkeypatch.setenv("PORTAL_EVIDENCE_S3_BUCKET", "portal-evidence-dev")
    monkeypatch.setenv("PORTAL_EVIDENCE_S3_ACCESS_KEY", "portal-dev-only")
    monkeypatch.setenv("PORTAL_EVIDENCE_S3_SECRET_KEY", "portal-dev-only")
    get_settings.cache_clear()
    storage.get_store.cache_clear()


def test_evidence_is_immutable_and_assets_stay_in_their_own_prefix(
    endpoint: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, endpoint)
    try:
        store = storage.get_store()
        stored = store.put("attempt/file/original", b"page")
        assert stored.sha256 == hashlib.sha256(b"page").hexdigest()
        assert store.get("attempt/file/original") == b"page"
        assert store.sha256("attempt/file/original") == stored.sha256
        with pytest.raises(FileExistsError):
            store.put("attempt/file/original", b"replaced")
        assert store.get("attempt/file/original") == b"page"
        assets._write("asset/version/master", b"diagram")
        assert assets.read("asset/version/master") == b"diagram"
        assert assets.delivery_bytes(_version("asset/version/master")) == len(b"diagram")
        listed = {key for key, _ in store.list_objects()}
        assert listed == {"attempt/file/original"}
        store.discard_uncommitted("attempt/file/original")
        assert not store.exists("attempt/file/original")
        assert store.sha256("missing/key") is None
        assets._remove("asset/version/master")
        with pytest.raises(FileNotFoundError):
            assets.read("asset/version/master")
        assert health(get_settings()) == "ok"
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        storage.get_store.cache_clear()


def test_an_unreachable_store_is_a_retryable_outage(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, "http://127.0.0.1:1")
    try:
        with pytest.raises(storage.EvidenceStoreUnavailable):
            storage.get_store().put("attempt/file/original", b"page")
        assert health(get_settings()) == "failing"
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        storage.get_store.cache_clear()


class _Version:
    delivery_state = "ready"

    def __init__(self, key: str) -> None:
        self.delivery_key = key


def _version(key: str) -> _Version:
    return _Version(key)
