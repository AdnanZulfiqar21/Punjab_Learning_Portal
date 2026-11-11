"""Access-token verification. Every token, from the portal's own password issuer or an external OIDC provider, goes
through the same checks: signature (the local key or JWKS), issuer, audience, expiry and required claims. Nothing here
trusts client claims about roles or entitlements; those are application data."""

from __future__ import annotations

import hashlib
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


class ProviderUnreachable(Exception):
    """The identity provider's signing keys could not be fetched (DEGRADATION-01). Says nothing about the token."""


@dataclass(frozen=True)
class Claims:
    issuer: str
    subject: str
    email: str | None
    token_id: str | None
    expires_at: int
    mfa: bool
    # P04.S3.T3: when the person last proved who they are (the provider's auth_time, else when the token was issued;
    # for an app session, when the session was created at sign-in). None when unknown.
    authenticated_at: int | None = None


class LocalIssuer:
    """The portal's own RS256 issuer for email + password accounts (AUTH-PASSWORD-01). Deployed roles load the signing
    key from `password_auth_signing_key`, so every process and restart signs and verifies with the same key; without
    one (development/test only, enforced by the configuration validator) a key is generated per process."""

    def __init__(self, issuer: str, audience: str, ttl_s: int, private_pem: str = "") -> None:
        self.issuer, self.audience, self.ttl_s = issuer, audience, ttl_s
        if private_pem.strip():
            key = serialization.load_pem_private_key(private_pem.strip().encode(), password=None)
            if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
                raise RuntimeError("password_auth_signing_key must be an RSA private key of at least 2048 bits")
            self._key = key
        else:
            self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_pem = self._key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.kid = hashlib.sha256(self.public_pem).hexdigest()[:16]

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


_local_issuer: LocalIssuer | None = None
_local_issuer_lock = threading.Lock()


def local_issuer_enabled(s: Settings) -> bool:
    return s.password_auth_enabled or s.dev_auth_enabled


def get_local_issuer() -> LocalIssuer:
    """One issuer per process. Built under a lock: `lru_cache` let concurrent first calls each generate a key, and
    tokens signed with a discarded key then failed verification (R08, a 401 right after sign-up)."""
    global _local_issuer
    issuer = _local_issuer
    if issuer is not None:
        return issuer
    with _local_issuer_lock:
        if _local_issuer is None:
            s = get_settings()
            if not local_issuer_enabled(s):
                raise RuntimeError("the local password issuer is disabled")
            _local_issuer = LocalIssuer(
                s.password_auth_issuer,
                s.password_auth_audience,
                s.password_auth_token_ttl_s,
                s.password_auth_signing_key.get_secret_value(),
            )
        return _local_issuer


def reset_local_issuer() -> None:
    """Tests only: forget the process issuer (tokens signed with a generated key stop verifying)."""
    global _local_issuer
    with _local_issuer_lock:
        _local_issuer = None


# Former names, kept for existing callers and tests.
DevIssuer = LocalIssuer
get_dev_issuer = get_local_issuer
reset_dev_issuer = reset_local_issuer


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

    if local_issuer_enabled(s) and issuer == s.password_auth_issuer:
        key: Any = get_local_issuer().public_pem
        audience = s.password_auth_audience
    elif s.oidc_issuer and issuer == s.oidc_issuer and s.jwks_url:
        try:
            key = _jwks_client(s.jwks_url).get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientConnectionError as e:
            raise ProviderUnreachable(str(e)) from e  # an outage, not a bad sign-in: retry, don't sign out
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
        authenticated_at=int(payload.get("auth_time") or payload["iat"]),
    )
