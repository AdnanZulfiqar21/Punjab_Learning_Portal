"""Private evidence storage (W03.S3.T1). Objects are immutable: a key is written once and never overwritten, so sealed
evidence can't be substituted. The server computes the checksum itself; a client-supplied hash is never trusted.

The local backend is a private directory for development/test. ``s3`` uses the path-style client in
``portal_api.object_store`` (a development emulator, or a private bucket once one is chosen — B03). The configuration
validator refuses to start a deployed role with the local directory or with the emulator's credentials.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from portal_api.config import get_settings
from portal_api.errors import StorageUnavailable
from portal_api.object_store import Client, ObjectStoreError, Prefixed


class EvidenceStoreUnavailable(StorageUnavailable):
    """The evidence store is not connected or can't take a write (DEGRADATION-01): a retryable 503, never a 500."""


@dataclass(frozen=True)
class Stored:
    key: str
    sha256: str
    size: int


class LocalEvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Keys are server-generated (attempt/page UUIDs); reject anything that could escape the root.
        if ".." in key or key.startswith(("/", "\\")) or ":" in key:
            raise ValueError("invalid evidence key")
        return self.root / key

    def put(self, key: str, data: bytes) -> Stored:
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise EvidenceStoreUnavailable() from e
        try:
            # Exclusive create: an existing object is never replaced.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        except FileExistsError:
            raise  # a key collision is a bug, not an outage
        except OSError as e:
            raise EvidenceStoreUnavailable() from e
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
        except OSError as e:
            path.unlink(missing_ok=True)  # never leave half an object behind
            raise EvidenceStoreUnavailable() from e
        return Stored(key=key, sha256=hashlib.sha256(data).hexdigest(), size=len(data))

    def discard_uncommitted(self, key: str) -> None:
        """Remove an object whose database row was never committed (a refused or failed admission). Committed
        evidence is never passed here; immutability applies to everything a row references."""
        self._path(key).unlink(missing_ok=True)

    def list_objects(self) -> list[tuple[str, float]]:
        """Every stored key with its modification time (orphan sweeps)."""
        out = []
        for path in self.root.rglob("*"):
            if path.is_file():
                out.append((path.relative_to(self.root).as_posix(), path.stat().st_mtime))
        return out

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def sha256(self, key: str) -> str | None:
        path = self._path(key)
        if not path.is_file():
            return None
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()


class S3EvidenceStore:
    """Immutable evidence in the shared bucket, under ``evidence/``. A key is written once."""

    def __init__(self, bucket: Prefixed) -> None:
        self.bucket = bucket

    def put(self, key: str, data: bytes) -> Stored:
        try:
            self.bucket.put(key, data, exclusive=True)
        except ObjectStoreError as e:
            raise EvidenceStoreUnavailable("Private file storage isn't connected yet. Please try again later.") from e
        return Stored(key=key, sha256=hashlib.sha256(data).hexdigest(), size=len(data))

    def discard_uncommitted(self, key: str) -> None:
        try:
            self.bucket.delete(key)
        except ObjectStoreError as e:
            raise EvidenceStoreUnavailable("Private file storage isn't connected yet. Please try again later.") from e

    def list_objects(self) -> list[tuple[str, float]]:
        try:
            return self.bucket.list()
        except ObjectStoreError as e:
            raise EvidenceStoreUnavailable("Private file storage isn't connected yet. Please try again later.") from e

    def get(self, key: str) -> bytes:
        try:
            return self.bucket.get(key)
        except ObjectStoreError as e:
            raise EvidenceStoreUnavailable("Private file storage isn't connected yet. Please try again later.") from e

    def exists(self, key: str) -> bool:
        try:
            return self.bucket.exists(key)
        except ObjectStoreError as e:
            raise EvidenceStoreUnavailable("Private file storage isn't connected yet. Please try again later.") from e

    def sha256(self, key: str) -> str | None:
        try:
            return hashlib.sha256(self.bucket.get(key)).hexdigest()
        except FileNotFoundError:
            return None
        except ObjectStoreError as e:
            raise EvidenceStoreUnavailable("Private file storage isn't connected yet. Please try again later.") from e


@lru_cache
def get_store() -> LocalEvidenceStore | S3EvidenceStore:
    s = get_settings()
    if s.evidence_store == "s3":
        try:
            client = Client(
                s.evidence_s3_endpoint,
                s.evidence_s3_bucket,
                s.evidence_s3_access_key,
                s.evidence_s3_secret_key,
                s.evidence_s3_region,
            )
        except ObjectStoreError as e:
            raise EvidenceStoreUnavailable("Private file storage isn't connected yet. Please try again later.") from e
        return S3EvidenceStore(client.prefixed("evidence/"))
    root = Path(s.evidence_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[4] / root  # apps/api/<evidence_dir>
    return LocalEvidenceStore(root)
