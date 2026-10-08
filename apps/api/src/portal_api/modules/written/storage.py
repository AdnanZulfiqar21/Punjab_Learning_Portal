"""Private evidence storage (W03.S3.T1). Objects are immutable: a key is written once and never overwritten, so sealed
evidence can't be substituted. The server computes the checksum itself; a client-supplied hash is never trusted.

The local backend is a private directory for development/test. Deployed roles must use private object storage (S3
proposed, BLOCKERS B03); the configuration validator refuses to start them with the local backend.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from portal_api.config import get_settings


class EvidenceStoreUnavailable(RuntimeError):
    pass


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
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive create: an existing object is never replaced.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
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


@lru_cache
def get_store() -> LocalEvidenceStore:
    s = get_settings()
    if s.evidence_store != "local":
        raise EvidenceStoreUnavailable("Private object storage isn't connected yet (BLOCKERS B03).")
    root = Path(s.evidence_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[4] / root  # apps/api/<evidence_dir>
    return LocalEvidenceStore(root)
