"""Access-token verification. Every token, from the managed OIDC provider or the dev-only local issuer, goes through
the same checks: signature (JWKS), issuer, audience, expiry and required claims. Nothing here trusts client claims
about roles or entitlements; those are application data."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from portal_api.config import Settings, get_settings

LEEWAY_S = 30
MFA_AMR = {"mfa", "otp", "hwk", "swk", "sms"}


class InvalidToken(Exception):
    """The presented credential is missing, malformed, expired or from an untrusted issuer."""


@dataclass(frozen=True)
class Claims:
    issuer: str
    subject: str
    email: str | None
    token_id: str | None
    expires_at: int
    mfa: bool


class DevIssuer:
    """In-process RSA issuer for development/test only. Keys are ephemeral (regenerated per process)."""

    def __init__(self, issuer: str, audience: str, ttl_s: int) -> None:
        self.issuer, self.audience, self.ttl_s = issuer, audience, ttl_s
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = uuid.uuid4().hex
        self.public_pem = self._key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def issue(self, subject: str, email: str | None, *, mfa: bool = False, ttl_s: int | None = None) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": subject,
            "iat": now,
            "exp": now + (ttl_s if ttl_s is not None else self.ttl_s),
            "jti": uuid.uuid4().hex,
            "token_use": "access",
            "amr": ["pwd", "mfa"] if mfa else ["pwd"],
        }
        if email:
            claims["email"] = email
        return jwt.encode(claims, self._key, algorithm="RS256", headers={"kid": self.kid})


_dev_issuer: DevIssuer | None = None
_dev_issuer_lock = threading.Lock()


def get_dev_issuer() -> DevIssuer:
    """One issuer per process. Built under a lock: `lru_cache` let concurrent first calls each generate a key, and
    tokens signed with a discarded key then failed verification (R08, a 401 right after sign-up)."""
    global _dev_issuer
    issuer = _dev_issuer
    if issuer is not None:
        return issuer
    with _dev_issuer_lock:
        if _dev_issuer is None:
            s = get_settings()
            if not s.dev_auth_enabled:
                raise RuntimeError("development issuer is disabled")
            _dev_issuer = DevIssuer(s.dev_auth_issuer, s.dev_auth_audience, s.dev_auth_token_ttl_s)
        return _dev_issuer


def reset_dev_issuer() -> None:
    """Tests only: forget the process issuer (its tokens stop verifying)."""
    global _dev_issuer
    with _dev_issuer_lock:
        _dev_issuer = None


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=5)


def verify(token: str, settings: Settings | None = None) -> Claims:
    s = settings or get_settings()
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as e:
        raise InvalidToken("malformed token") from e
    issuer = unverified.get("iss")

    if s.dev_auth_enabled and issuer == s.dev_auth_issuer:
        key: Any = get_dev_issuer().public_pem
        audience = s.dev_auth_audience
    elif s.oidc_issuer and issuer == s.oidc_issuer and s.jwks_url:
        try:
            key = _jwks_client(s.jwks_url).get_signing_key_from_jwt(token).key
        except jwt.PyJWTError as e:
            raise InvalidToken("unknown signing key") from e
        audience = s.oidc_audience or ""
    else:
        raise InvalidToken("untrusted issuer")

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            leeway=LEEWAY_S,
            options={"require": ["exp", "iat", "iss", "sub"], "verify_aud": False},
        )
    except jwt.PyJWTError as e:
        raise InvalidToken(str(e)) from e
    # Cognito access tokens carry the app client in client_id instead of aud; ID/other tokens use aud.
    aud = payload.get("aud") or payload.get("client_id")
    auds = aud if isinstance(aud, list) else [aud]
    if audience not in auds:
        raise InvalidToken("audience mismatch")
    if payload.get("token_use") not in (None, "access"):
        raise InvalidToken("not an access token")
    amr = set(payload.get("amr") or [])
    return Claims(
        issuer=issuer,
        subject=str(payload["sub"]),
        email=(payload.get("email") or None),
        token_id=payload.get("jti"),
        expires_at=int(payload["exp"]),
        mfa=bool(amr & MFA_AMR),
    )
