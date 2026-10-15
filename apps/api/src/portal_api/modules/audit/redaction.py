"""Redacting sensitive values from audit details (AUDIT-01), shared by the audit explorer and the audit export.

Kept out of the router so other modules can use it without importing a router (MODULES-01: routers are leaves)."""

from __future__ import annotations

from typing import Any

SENSITIVE = ("email", "token", "hash", "password", "secret", "destination", "ip", "phone")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: "[redacted]" if any(s in k.lower() for s in SENSITIVE) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value
