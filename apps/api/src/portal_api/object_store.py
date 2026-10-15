"""S3-compatible object storage (P03.S1.T2).

Path-style requests only: ``{endpoint}/{bucket}/{prefix}{key}``. The local emulator (see
``infra/docker-compose.yml``) and a future private bucket use the same client. The production account and its region
are not chosen here (B03, D14). Evidence and lesson assets share one bucket under different prefixes so a key from
one can never read the other.

Objects are addressed by a server-generated key. A key that could leave its prefix is rejected before any request.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from datetime import UTC, datetime
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from portal_api.config import Settings

_UNRESERVED = "-_.~"


class ObjectStoreError(Exception):
    """The configured store could not be reached. Callers turn this into a retryable outage."""


def _encode(value: str) -> str:
    return quote(value, safe=_UNRESERVED)


def _canonical_uri(path: str) -> str:
    return "/".join(_encode(part) for part in path.split("/"))


def _canonical_query(query: Mapping[str, str]) -> str:
    return "&".join(f"{_encode(k)}={_encode(query[k])}" for k in sorted(query))


def signed_headers(
    *,
    method: str,
    host: str,
    path: str,
    query: Mapping[str, str],
    body: bytes,
    access_key: str,
    secret_key: str,
    region: str,
    now: datetime,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """SigV4 headers for one request. ``now`` is fixed in the published-example test."""
    payload = hashlib.sha256(body).hexdigest()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    scope_date = now.strftime("%Y%m%d")
    headers = {"host": host, "x-amz-content-sha256": payload, "x-amz-date": amz_date, **(extra or {})}
    lowered = [(k.lower().strip(), " ".join(v.strip().split())) for k, v in headers.items()]
    lowered.sort()
    canonical_headers = "".join(f"{k}:{v}\n" for k, v in lowered)
    signed = ";".join(k for k, _ in lowered)
    canonical = "\n".join([method, _canonical_uri(path), _canonical_query(query), canonical_headers, signed, payload])
    scope = f"{scope_date}/{region}/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    key = ("AWS4" + secret_key).encode()
    for part in (scope_date, region, "s3", "aws4_request"):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={signed}, Signature={signature}"
    )
    return headers


def _check_key(key: str) -> str:
    # The same rule as the local directory store: server-generated keys only, nothing that could escape a prefix.
    if not key or key.startswith(("/", "\\")) or "\\" in key or ":" in key or ".." in key:
        raise ValueError("invalid object key")
    return key


class Client:
    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str, region: str) -> None:
        parsed = urlsplit(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path not in ("", "/"):
            raise ObjectStoreError("The object-storage endpoint must be an http(s) origin.")
        if not region.replace("-", "").isalnum():
            raise ObjectStoreError("The object-storage region must be a signing name, not markup.")
        self.endpoint = endpoint.rstrip("/")
        self.host = parsed.netloc
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self._ready = False

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
        body: bytes = b"",
        extra: Mapping[str, str] | None = None,
        timeout: float = 5,
    ) -> tuple[int, Message, bytes]:
        query = query or {}
        headers = signed_headers(
            method=method,
            host=self.host,
            path=path,
            query=query,
            body=body,
            access_key=self.access_key,
            secret_key=self.secret_key,
            region=self.region,
            now=datetime.now(UTC),
            extra=extra,
        )
        url = self.endpoint + path
        if query:
            url += "?" + _canonical_query(query)
        req = Request(url, data=body if method != "HEAD" else None, headers=headers, method=method)  # noqa: S310
        try:
            with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — http(s) only; the endpoint is configuration
                return resp.status, resp.headers, resp.read()
        except HTTPError as e:
            return e.code, e.headers, e.read()
        except (URLError, TimeoutError, OSError) as e:
            raise ObjectStoreError("Private file storage isn't connected yet. Please try again later.") from e

    def ensure_bucket(self) -> None:
        if self._ready:
            return
        body = b""
        if self.region != "us-east-1":
            body = (
                '<CreateBucketConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                f"<LocationConstraint>{self.region}</LocationConstraint></CreateBucketConfiguration>"
            ).encode()
        status, _, _ = self.request("PUT", f"/{self.bucket}", body=body)
        if status not in (200, 409):
            raise ObjectStoreError("Private file storage isn't connected yet. Please try again later.")
        self._ready = True

    def prefixed(self, prefix: str) -> Prefixed:
        return Prefixed(self, prefix)


class Prefixed:
    """One prefix inside the bucket. Returned keys never include the prefix."""

    def __init__(self, client: Client, prefix: str) -> None:
        if not prefix.endswith("/"):
            raise ValueError("prefix must end with /")
        self.client = client
        self.prefix = prefix

    def _path(self, key: str) -> str:
        return f"/{self.client.bucket}/{self.prefix}{_check_key(key)}"

    def put(self, key: str, data: bytes, *, exclusive: bool) -> None:
        self.client.ensure_bucket()
        extra = {"if-none-match": "*"} if exclusive else {}
        status, _, _ = self.client.request("PUT", self._path(key), body=data, extra=extra)
        if exclusive and status in (409, 412):
            raise FileExistsError(key)
        if status not in (200, 201):
            raise ObjectStoreError("Private file storage isn't connected yet. Please try again later.")

    def get(self, key: str) -> bytes:
        status, _, body = self.client.request("GET", self._path(key))
        if status == 404:
            raise FileNotFoundError(key)
        if status != 200:
            raise ObjectStoreError("Private file storage isn't connected yet. Please try again later.")
        return body

    def delete(self, key: str) -> None:
        status, _, _ = self.client.request("DELETE", self._path(key))
        if status not in (200, 204, 404):
            raise ObjectStoreError("Private file storage isn't connected yet. Please try again later.")

    def exists(self, key: str) -> bool:
        status, _, _ = self.client.request("HEAD", self._path(key))
        if status == 404:
            return False
        if status != 200:
            raise ObjectStoreError("Private file storage isn't connected yet. Please try again later.")
        return True

    def size(self, key: str) -> int:
        status, headers, _ = self.client.request("HEAD", self._path(key))
        if status == 404:
            raise FileNotFoundError(key)
        if status != 200:
            raise ObjectStoreError("Private file storage isn't connected yet. Please try again later.")
        return int(headers.get("Content-Length", "0"))

    def list(self) -> list[tuple[str, float]]:
        out: list[tuple[str, float]] = []
        token = ""
        while True:
            query = {"list-type": "2", "max-keys": "1000", "prefix": self.prefix}
            if token:
                query["continuation-token"] = token
            status, _, body = self.client.request("GET", f"/{self.client.bucket}", query=query)
            if status != 200:
                raise ObjectStoreError("Private file storage isn't connected yet. Please try again later.")
            if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
                raise ObjectStoreError("Private file storage isn't connected yet. Please try again later.")
            try:
                root = ElementTree.fromstring(body)  # noqa: S314 — a doctype or entity was refused just above
            except ElementTree.ParseError as e:
                raise ObjectStoreError("Private file storage isn't connected yet. Please try again later.") from e
            for node in root.iter():
                if _local(node.tag) != "Contents":
                    continue
                name = _child(node, "Key")
                if not name.startswith(self.prefix):
                    continue
                logical = name[len(self.prefix) :]
                if not logical:
                    continue
                stamp = _child(node, "LastModified")
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp() if stamp else 0.0
                out.append((logical, when))
            if _child(root, "IsTruncated") != "true":
                return out
            token = _child(root, "NextContinuationToken")
            if not token:
                return out


def health(settings: Settings) -> str:
    """HEAD the bucket. No secret, URL or object name is returned."""
    try:
        client = Client(
            settings.evidence_s3_endpoint,
            settings.evidence_s3_bucket,
            settings.evidence_s3_access_key,
            settings.evidence_s3_secret_key,
            settings.evidence_s3_region,
        )
        status, _, _ = client.request("HEAD", f"/{client.bucket}")
    except (ObjectStoreError, ValueError):
        return "failing"
    return "ok" if status == 200 else "failing"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(node: ElementTree.Element, name: str) -> str:
    for child in list(node):
        if _local(child.tag) == name and child.text:
            return child.text
    return ""
