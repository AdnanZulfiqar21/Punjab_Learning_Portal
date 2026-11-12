"""Sending one email through the configured adapter (AUTH-PASSWORD-01, P15.S1.T2).

* ``resend``: Resend's HTTPS API (https://resend.com/docs/api-reference/emails/send-email) with the deployment's API
  key, from ``email_from`` on a domain verified in Resend.
* ``dev_outbox``: development/test only (refused in staging/production by the configuration validator). Nothing leaves
  the machine: the message is logged and kept in a short in-process list that tests and the development code lookup
  read.
* ``none``: nothing is sent and the caller is told so (DEGRADATION-01: never reported as sent).

No database connection is used here, so callers must not hold one open while sending (review R08).
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime

from portal_api.config import get_settings

log = logging.getLogger("portal.email")
TIMEOUT_S = 10


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    text: str
    html: str
    tag: str  # what kind of message, for logs and the outbox (never personal data)


@dataclass(frozen=True)
class SendResult:
    status: str  # sent | failed | unavailable
    ref: str | None = None
    error: str | None = None
    retryable: bool = False


@dataclass(frozen=True)
class OutboxEntry:
    message: Message
    at: datetime


_OUTBOX: deque[OutboxEntry] = deque(maxlen=200)
_OUTBOX_LOCK = threading.Lock()


def outbox() -> list[OutboxEntry]:
    """Development/test only: the messages the dev outbox recorded in this process, oldest first."""
    with _OUTBOX_LOCK:
        return list(_OUTBOX)


def clear_outbox() -> None:
    with _OUTBOX_LOCK:
        _OUTBOX.clear()


def send(message: Message, *, idempotency_key: str | None = None) -> SendResult:
    s = get_settings()
    adapter = s.notification_email_adapter
    if adapter == "none":
        return SendResult("unavailable", error="no email sender is configured")
    if adapter == "dev_outbox":
        with _OUTBOX_LOCK:
            _OUTBOX.append(OutboxEntry(message, datetime.now(UTC)))
        # Development only: the body is logged so a developer can read a code without a real inbox.
        log.info("dev email tag=%s to=%s subject=%r\n%s", message.tag, message.to, message.subject, message.text)
        return SendResult("sent", ref="dev-outbox")
    if adapter == "resend":
        return _send_resend(message, idempotency_key)
    return SendResult("unavailable", error=f"email adapter {adapter!r} is not implemented; nothing was sent")


def _send_resend(message: Message, idempotency_key: str | None) -> SendResult:
    s = get_settings()
    body = json.dumps(
        {
            "from": s.email_from,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text,
            "html": message.html,
            "tags": [{"name": "kind", "value": message.tag}],
        }
    ).encode()
    headers = {
        "Authorization": f"Bearer {s.resend_api_key.get_secret_value()}",
        "Content-Type": "application/json",
        "User-Agent": "portal-api",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key[:256]
    req = urllib.request.Request(s.resend_api_url, data=body, headers=headers, method="POST")  # noqa: S310 (https URL from configuration)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310
            data = json.loads(resp.read() or b"{}")
        ref = str(data.get("id") or "") or None
        log.info("email sent via resend tag=%s id=%s", message.tag, ref)
        return SendResult("sent", ref=ref)
    except urllib.error.HTTPError as e:
        detail = _error_text(e)
        # 429 and 5xx are worth trying again later; other 4xx (bad key, unverified domain, invalid address) are not.
        retryable = e.code == 429 or e.code >= 500
        log.warning("resend refused tag=%s status=%s %s", message.tag, e.code, detail)
        return SendResult("failed", error=f"resend {e.code}: {detail}", retryable=retryable)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        log.warning("resend unreachable tag=%s %s", message.tag, e)
        return SendResult("failed", error=f"resend unreachable: {e}", retryable=True)


def _error_text(e: urllib.error.HTTPError) -> str:
    try:
        data = json.loads(e.read() or b"{}")
        return str(data.get("message") or data.get("name") or "")[:300]
    except (ValueError, OSError):
        return ""
