"""Trial claims, device authorization and recovery (roadmap §16.2-16.4, P14.S5/S6; review R06; decision TRIAL-02).

The account grant (`trial_grant`, one per account and program) and device authorization (`trial_device_use`) are
separate. A claim is the durable, idempotent record of one activation attempt and its evidence, created *before* any
remote consumption marker is written and moved through auditable states:

    PENDING_VERIFICATION -> MARK_PENDING -> MARK_CONFIRMED | MARK_UNKNOWN -> GRANTED
    ... or REVIEW_REQUIRED (older than the 7-day recovery window, or a consumed device) or CLOSED_INELIGIBLE

Device evidence comes from a per-surface adapter. Apple DeviceCheck/App Attest and Google Play Integrity with device
recall need store accounts and approval (BLOCKERS B07, B08), so their adapters report **unknown, provider not
configured** and never invent a verdict. A deterministic fixture adapter exists for development/test only.

Evidence mode (setting `trial_device_evidence`):
* `required`: unknown evidence never completes a native claim or device authorization (retry, review or support).
* `fallback`: while a provider is not configured, native activation proceeds on account history alone. The claim and
  device record say so (`evidence: provider_unconfigured`), so the same-device requirement is **not** claimed as met.
Deployed roles must choose the mode explicitly. Web activation always uses account history (§16.3: a browser is not a
device identity).

Installation references are salted hashes of an opaque per-install token chosen by the app. They are not device
identifiers, do not survive reinstall, and are never treated as reinstall-proof identity (§16.3).
"""

from __future__ import annotations

import hashlib
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, Protocol

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.config import Role as DeployRole
from portal_api.config import get_settings
from portal_api.db import Base
from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.access.models import OFFER_TERMS_VERSION, TRIAL_PROGRAM, Entitlement, TrialGrant
from portal_api.modules.audit.models import record

# (X-Portal-Client, X-Portal-Install) of the current request, set by middleware; read by entitlement checks.
CLIENT_CONTEXT: ContextVar[tuple[str | None, str | None]] = ContextVar("portal_client", default=(None, None))
RECOVERY_WINDOW = timedelta(days=7)  # T3: automatic recovery of an unresolved claim
MAX_TRIAL_DEVICES = 3  # T4 / D07 (proposed): concurrently registered trial devices per account
REPLACEMENT_WINDOW = timedelta(days=7)  # T4: one self-service replacement per 7 days
CLAIM_STATES = (
    "PENDING_VERIFICATION",
    "MARK_PENDING",
    "MARK_UNKNOWN",
    "MARK_CONFIRMED",
    "GRANTED",
    "REVIEW_REQUIRED",
    "CLOSED_INELIGIBLE",
)
Surface = Literal["web", "ios", "android"]


# ------------------------------------------------------------------ records
class TrialClaim(Base):
    __tablename__ = "trial_claim"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_trial_claim_key"),
        CheckConstraint(f"status in ({', '.join(repr(s) for s in CLAIM_STATES)})", name="trial_claim_status"),
        CheckConstraint("surface in ('web','ios','android')", name="trial_claim_surface"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    program: Mapped[str] = mapped_column(String(40), default=TRIAL_PROGRAM)
    offer_terms_version: Mapped[int] = mapped_column(default=OFFER_TERMS_VERSION)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    surface: Mapped[str] = mapped_column(String(10))
    installation_ref: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="PENDING_VERIFICATION")
    outcome: Mapped[str | None] = mapped_column(String(40))  # machine-readable reason for the current state
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict
    )  # adapter, verdict, mark result; no identifiers
    grant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("trial_grant.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrialClaimEvent(Base):
    __tablename__ = "trial_claim_event"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trial_claim.id", ondelete="RESTRICT"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrialDeviceUse(Base):
    """An approved relationship between one installation (or browser profile) and the account's trial grant."""

    __tablename__ = "trial_device_use"
    __table_args__ = (
        CheckConstraint("status in ('authorized','removed')", name="trial_device_use_status"),
        CheckConstraint(
            "method in ('first_use','recovery','exception','fallback','web')", name="trial_device_use_method"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trial_grant.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    surface: Mapped[str] = mapped_column(String(10))
    installation_ref: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(80), default="")
    method: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10), default="authorized")
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    replaces_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("trial_device_use.id", ondelete="RESTRICT"))
    authorized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrialException(Base):
    """An audited, account-scoped, time-bounded exception for a family/shared/second-hand device (§16.7)."""

    __tablename__ = "trial_exception"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    surface: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(Text)
    granted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ------------------------------------------------------------------ evidence adapters
@dataclass(frozen=True)
class Verdict:
    """What a provider can say about prior promotional use on this device. `unknown` is never clean or consumed."""

    status: Literal["clean", "consumed", "unknown", "not_applicable"]
    detail: str


class EvidenceAdapter(Protocol):
    name: str

    def evaluate(self, proof: dict[str, Any]) -> Verdict: ...

    def mark_consumed(self, proof: dict[str, Any]) -> Literal["confirmed", "unknown"]: ...


class WebAdapter:
    """Web/PWA: no device recall exists (§16.3). Eligibility is account and contact history; disclosed limits."""

    name = "web"

    def evaluate(self, proof: dict[str, Any]) -> Verdict:
        return Verdict("not_applicable", "browser profiles are not device identities")

    def mark_consumed(self, proof: dict[str, Any]) -> Literal["confirmed", "unknown"]:
        return "confirmed"  # the account ledger is the record for web


class UnconfiguredProvider:
    """Apple DeviceCheck/App Attest or Google Play Integrity + device recall before their accounts exist (B07/B08)."""

    def __init__(self, name: str, blocker: str) -> None:
        self.name = name
        self.blocker = blocker

    def evaluate(self, proof: dict[str, Any]) -> Verdict:
        return Verdict("unknown", f"provider_unconfigured ({self.blocker})")

    def mark_consumed(self, proof: dict[str, Any]) -> Literal["confirmed", "unknown"]:
        return "unknown"


class FixtureProvider:
    """Development/test only: deterministic verdicts for contract tests. Never evidence about a physical device."""

    def __init__(self, name: str) -> None:
        self.name = f"fixture-{name}"

    def evaluate(self, proof: dict[str, Any]) -> Verdict:
        v = proof.get("fixture_verdict", "unknown")
        if v not in ("clean", "consumed", "unknown"):
            raise Unprocessable("Unknown fixture verdict.")
        return Verdict(v, "technical fixture")

    def mark_consumed(self, proof: dict[str, Any]) -> Literal["confirmed", "unknown"]:
        return "unknown" if proof.get("fixture_mark") == "lost" else "confirmed"


def adapter_for(surface: str, proof: dict[str, Any]) -> EvidenceAdapter:
    if surface == "web":
        return WebAdapter()
    if "fixture_verdict" in proof:
        if get_settings().role not in (DeployRole.development, DeployRole.test):
            raise Unprocessable("Fixture evidence is accepted only in development and test.")
        return FixtureProvider(surface)
    if surface == "ios":
        return UnconfiguredProvider("apple-devicecheck", "B07")
    return UnconfiguredProvider("google-play-integrity-recall", "B07/B08")


def evidence_mode() -> str:
    s = get_settings()
    return s.trial_device_evidence or "fallback"  # dev/test default; deployed roles must set it (validator)


def installation_ref(token: str | None) -> str | None:
    if not token:
        return None
    if len(token) < 16 or len(token) > 200:
        raise Unprocessable("The installation token must be 16 to 200 characters.")
    pepper = get_settings().trial_ref_pepper
    return hashlib.sha256(f"{pepper}:{token}".encode()).hexdigest()


# ------------------------------------------------------------------ helpers
def _now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


def _lock_account(db: Session, user_id: uuid.UUID) -> None:
    """§16.4.7: claims, grants and purchases for one account/program serialize on the same boundary."""
    digest = hashlib.sha256(f"trial:{TRIAL_PROGRAM}:{user_id}".encode()).digest()
    db.execute(select(func.pg_advisory_xact_lock(int.from_bytes(digest[:8], "big", signed=True))))


def _move(db: Session, claim: TrialClaim, to: str, reason: str, outcome: str | None = None) -> None:
    now = _now(db)
    db.add(TrialClaimEvent(claim_id=claim.id, from_status=claim.status, to_status=to, reason=reason, at=now))
    claim.status = to
    claim.outcome = outcome
    claim.updated_at = now


def _grant(db: Session, user_id: uuid.UUID) -> TrialGrant | None:
    return db.scalar(select(TrialGrant).where(TrialGrant.user_id == user_id, TrialGrant.program == TRIAL_PROGRAM))


def _independent_access(db: Session, user_id: uuid.UUID, now: datetime) -> bool:
    """Valid paid, scholarship, promotional or pilot access: a trial decision never blocks it (§16.2.1)."""
    return bool(
        db.scalar(
            select(Entitlement.id).where(
                Entitlement.user_id == user_id,
                Entitlement.status == "active",
                Entitlement.source != "trial",
                Entitlement.starts_at <= now,
                Entitlement.ends_at > now,
            )
        )
    )


def _paid_history(db: Session, user_id: uuid.UUID) -> bool:
    return bool(db.scalar(select(Entitlement.id).where(Entitlement.user_id == user_id, Entitlement.source == "paid")))


def active_devices(db: Session, grant_id: uuid.UUID) -> list[TrialDeviceUse]:
    return list(
        db.scalars(
            select(TrialDeviceUse)
            .where(TrialDeviceUse.grant_id == grant_id, TrialDeviceUse.status == "authorized")
            .order_by(TrialDeviceUse.authorized_at)
        )
    )


def _active_exception(db: Session, user_id: uuid.UUID, surface: str, now: datetime) -> TrialException | None:
    return db.scalar(
        select(TrialException).where(
            TrialException.user_id == user_id,
            TrialException.surface == surface,
            TrialException.expires_at > now,
        )
    )


# ------------------------------------------------------------------ decisions
@dataclass
class Decision:
    state: str  # eligible | granted | active | paid_active | review_required | device_used | account_trial_used |
    # prior_paid | verification_pending | device_limit | device_authorized
    claim: TrialClaim | None = None
    grant: TrialGrant | None = None
    device: TrialDeviceUse | None = None
    message: str = ""


MESSAGES = {  # §16.5 notices (English; reviewed Urdu/Roman Urdu equivalents are a content task)
    "granted": "Your free trial has started.",
    "active": "Your free trial is active.",
    "device_authorized": "This device can use your free trial.",
    "paid_active": "Your subscription is active.",
    "account_trial_used": "Your trial period has already been used. Please subscribe to continue learning.",
    "prior_paid": "The free trial is for new learners. Your account has had a paid plan.",
    "device_used": "A free trial has already been used on this device. Sign in to your existing account or subscribe "
    "to continue.",
    "review_required": "We need to review trial use on this device. Sign in to your existing account, subscribe, or "
    "contact support for a private review.",
    "verification_pending": "We could not verify your trial eligibility. Please try again or contact support.",
    "device_limit": "This trial is already in use on the maximum number of devices. "
    "Remove a device or contact support.",
}


def _decision(state: str, **kw: Any) -> Decision:
    return Decision(state=state, message=MESSAGES.get(state, ""), **kw)


def claim(
    db: Session,
    user_id: uuid.UUID,
    *,
    surface: Surface,
    idempotency_key: str,
    proof: dict[str, Any],
    install_token: str | None,
    label: str = "",
) -> Decision:
    """Start (or recover) the one trial for this account, following §16.2 in order."""
    from portal_api.modules.access import service as access

    if surface != "web" and not install_token:
        raise Unprocessable("The app must send its installation token to activate a trial.")
    ref = installation_ref(install_token)
    _lock_account(db, user_id)
    now = _now(db)
    existing = db.scalar(
        select(TrialClaim).where(TrialClaim.user_id == user_id, TrialClaim.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return _resume(db, existing, proof, label)

    # 1. Independent valid access is honored and never blocked by a trial decision.
    if _independent_access(db, user_id, now):
        db.commit()
        return _decision("paid_active")
    grant = _grant(db, user_id)
    # 2. An existing grant: keep its dates; a new native device needs its own authorization (§16.4).
    if grant is not None:
        if grant.status == "active" and grant.ends_at > now:
            if surface == "web":
                device = _record_web(db, grant, ref, label, now)
                db.commit()
                return _decision("active", grant=grant, device=device)
            db.commit()
            return authorize_device(db, user_id, surface=surface, proof=proof, install_token=install_token, label=label)
        db.commit()
        return _decision("account_trial_used", grant=grant)
    # 3. Prior paid history (T8): no introductory trial.
    if _paid_history(db, user_id):
        db.commit()
        return _decision("prior_paid")

    # 4. A genuinely new claim: persisted before any remote marker write.
    c = TrialClaim(
        user_id=user_id,
        idempotency_key=idempotency_key,
        surface=surface,
        installation_ref=ref,
        status="PENDING_VERIFICATION",
        created_at=now,
        updated_at=now,
    )
    db.add(c)
    db.flush()
    db.add(TrialClaimEvent(claim_id=c.id, from_status=None, to_status=c.status, reason="claim created", at=now))
    adapter = adapter_for(surface, proof)
    verdict = adapter.evaluate(proof)
    c.evidence = {"adapter": adapter.name, "verdict": verdict.status, "detail": verdict.detail, "mode": evidence_mode()}
    if verdict.status == "consumed":
        # 5. A consumed marker with no grant on this account: no automatic repeat redemption (§16.4).
        _move(db, c, "CLOSED_INELIGIBLE", "prior promotional use recorded for this device", "device_used")
        record(
            db,
            actor=user_id,
            action="trial.claim_denied",
            target_type="trial_claim",
            target_id=str(c.id),
            details={"surface": surface, "verdict": "consumed"},
        )
        db.commit()
        return _decision("device_used", claim=c)
    if verdict.status == "unknown" and not _fallback_allows(verdict):
        _move(db, c, "PENDING_VERIFICATION", "evidence unknown; retry or review", "verification_pending")
        db.commit()
        return _decision("verification_pending", claim=c)
    return _mark_and_grant(db, c, adapter, proof, label, access)


def _fallback_allows(verdict: Verdict) -> bool:
    return evidence_mode() == "fallback" and verdict.detail.startswith("provider_unconfigured")


def _mark_and_grant(
    db: Session, c: TrialClaim, adapter: EvidenceAdapter, proof: dict[str, Any], label: str, access: Any
) -> Decision:
    if c.evidence.get("verdict") in ("clean",):
        _move(db, c, "MARK_PENDING", "writing the consumption marker")
        db.flush()
        result = adapter.mark_consumed(proof)
        c.evidence = {**c.evidence, "mark": result}
        if result != "confirmed":
            _move(db, c, "MARK_UNKNOWN", "marker write outcome unknown; recover with the same claim", "mark_unknown")
            db.commit()
            return _decision("verification_pending", claim=c)
        _move(db, c, "MARK_CONFIRMED", "consumption marker confirmed")
    # Final eligibility re-check and grant creation under the account lock (§16.4.4).
    now = _now(db)
    if _grant(db, c.user_id) is not None or _paid_history(db, c.user_id):
        _move(db, c, "CLOSED_INELIGIBLE", "account history changed before the grant", "account_trial_used")
        db.commit()
        return _decision("account_trial_used", claim=c)
    grant = access.create_trial_grant(db, c.user_id, client="web" if c.surface == "web" else "native")
    c.grant_id = grant.id
    _move(db, c, "GRANTED", "trial granted")
    method = "web" if c.surface == "web" else ("fallback" if c.evidence.get("verdict") == "unknown" else "first_use")
    device = None
    if c.installation_ref:
        device = TrialDeviceUse(
            grant_id=grant.id,
            user_id=c.user_id,
            surface=c.surface,
            installation_ref=c.installation_ref,
            label=label[:80],
            method=method,
            evidence=c.evidence,
            authorized_at=now,
        )
        db.add(device)
    record(
        db,
        actor=c.user_id,
        action="trial.claim_granted",
        target_type="trial_claim",
        target_id=str(c.id),
        details={"surface": c.surface, "evidence": c.evidence, "grant": str(grant.id)},
    )
    db.commit()
    db.refresh(grant)
    return _decision("granted", claim=c, grant=grant, device=device)


def _resume(db: Session, c: TrialClaim, proof: dict[str, Any], label: str) -> Decision:
    """A retry of the same claim (§16.4.3/5/6): the original grant and dates, or recovery of an unresolved claim."""
    from portal_api.modules.access import service as access

    now = _now(db)
    if c.status == "GRANTED":
        grant = db.get(TrialGrant, c.grant_id)
        db.commit()
        return _decision("granted", claim=c, grant=grant)
    if c.status == "CLOSED_INELIGIBLE":
        db.commit()
        return _decision(c.outcome or "account_trial_used", claim=c)
    if c.status == "REVIEW_REQUIRED":
        db.commit()
        return _decision("review_required", claim=c)
    if now - c.created_at > RECOVERY_WINDOW:
        _move(db, c, "REVIEW_REQUIRED", "unresolved after the 7-day recovery window", "review_required")
        db.commit()
        return _decision("review_required", claim=c)
    adapter = adapter_for(c.surface, proof)
    if c.status in ("MARK_UNKNOWN", "MARK_PENDING"):
        result = adapter.mark_consumed(proof)  # re-attempt the original claim's marker; never a replacement claim
        c.evidence = {**c.evidence, "mark": result}
        if result != "confirmed":
            db.commit()
            return _decision("verification_pending", claim=c)
        _move(db, c, "MARK_CONFIRMED", "consumption marker confirmed on recovery")
        c.evidence = {**c.evidence, "verdict": "clean"}
        return _mark_and_grant(db, c, _Confirmed(), proof, label, access)
    if c.status == "MARK_CONFIRMED":
        return _mark_and_grant(db, c, _Confirmed(), proof, label, access)
    # PENDING_VERIFICATION: evaluate again with fresh proof.
    verdict = adapter.evaluate(proof)
    c.evidence = {**c.evidence, "verdict": verdict.status, "detail": verdict.detail, "mode": evidence_mode()}
    if verdict.status == "consumed":
        _move(db, c, "CLOSED_INELIGIBLE", "prior promotional use recorded for this device", "device_used")
        db.commit()
        return _decision("device_used", claim=c)
    if verdict.status == "unknown" and not _fallback_allows(verdict):
        db.commit()
        return _decision("verification_pending", claim=c)
    return _mark_and_grant(db, c, adapter, proof, label, access)


class _Confirmed:
    name = "confirmed"

    def evaluate(self, proof: dict[str, Any]) -> Verdict:
        return Verdict("clean", "marker already confirmed for this claim")

    def mark_consumed(self, proof: dict[str, Any]) -> Literal["confirmed", "unknown"]:
        return "confirmed"


def _record_web(db: Session, grant: TrialGrant, ref: str | None, label: str, now: datetime) -> TrialDeviceUse | None:
    if ref is None:
        return None
    existing = db.scalar(
        select(TrialDeviceUse).where(
            TrialDeviceUse.grant_id == grant.id,
            TrialDeviceUse.installation_ref == ref,
            TrialDeviceUse.status == "authorized",
        )
    )
    if existing is not None:
        return existing
    if len(active_devices(db, grant.id)) >= MAX_TRIAL_DEVICES:
        return None  # browser profiles count toward the limit; the account's trial itself is unaffected on web
    use = TrialDeviceUse(
        grant_id=grant.id,
        user_id=grant.user_id,
        surface="web",
        installation_ref=ref,
        label=label[:80],
        method="web",
        authorized_at=now,
    )
    db.add(use)
    return use


def authorize_device(
    db: Session,
    user_id: uuid.UUID,
    *,
    surface: Surface,
    proof: dict[str, Any],
    install_token: str | None,
    label: str = "",
    replaces: uuid.UUID | None = None,
) -> Decision:
    """First trial use of an additional native device for an active grant (§16.4 decision table)."""
    ref = installation_ref(install_token)
    if ref is None:
        raise Unprocessable("The app must send its installation token.")
    _lock_account(db, user_id)
    now = _now(db)
    if _independent_access(db, user_id, now):
        db.commit()
        return _decision("paid_active")
    grant = _grant(db, user_id)
    if grant is None:
        db.commit()
        return _decision("eligible")
    if grant.status != "active" or grant.ends_at <= now:
        db.commit()
        return _decision("account_trial_used", grant=grant)
    current = db.scalar(
        select(TrialDeviceUse).where(
            TrialDeviceUse.grant_id == grant.id,
            TrialDeviceUse.installation_ref == ref,
            TrialDeviceUse.status == "authorized",
        )
    )
    if current is not None:  # already-authorized same-grant use continues
        db.commit()
        return _decision("device_authorized", grant=grant, device=current)

    exception = _active_exception(db, user_id, surface, now)
    adapter = adapter_for(surface, proof)
    verdict = adapter.evaluate(proof)
    evidence = {"adapter": adapter.name, "verdict": verdict.status, "detail": verdict.detail, "mode": evidence_mode()}
    method = "first_use"
    if exception is not None:
        method = "exception"
    elif verdict.status == "consumed":
        # A consumed marker plus an active grant is not a relationship to *this* grant (T2): review, never a new grant.
        record(
            db,
            actor=user_id,
            action="trial.device_review_required",
            target_type="trial_grant",
            target_id=str(grant.id),
            details={"surface": surface},
        )
        db.commit()
        return _decision("review_required", grant=grant)
    elif verdict.status == "unknown":
        if not _fallback_allows(verdict):
            db.commit()
            return _decision("verification_pending", grant=grant)
        method = "fallback"

    devices = active_devices(db, grant.id)
    old = None
    if replaces is not None:
        old = next((d for d in devices if d.id == replaces), None)
        if old is None:
            raise NotFound("That device isn't registered for your trial.")
        recent = db.scalar(
            select(TrialDeviceUse.id).where(
                TrialDeviceUse.user_id == user_id,
                TrialDeviceUse.replaces_id.is_not(None),
                TrialDeviceUse.authorized_at > now - REPLACEMENT_WINDOW,
            )
        )
        if recent is not None:
            raise Conflict(
                "You can replace one trial device every 7 days. Contact support for another replacement.",
                code_reason="REPLACEMENT_LIMIT",
            )
    elif len(devices) >= MAX_TRIAL_DEVICES:
        db.commit()
        return _decision("device_limit", grant=grant)
    if method == "first_use":
        mark = adapter.mark_consumed(proof)  # written on first trial use of this device only (T4)
        evidence["mark"] = mark
        if mark != "confirmed":
            db.commit()
            return _decision("verification_pending", grant=grant)
    if old is not None:
        old.status = "removed"
        old.removed_at = now
    use = TrialDeviceUse(
        grant_id=grant.id,
        user_id=user_id,
        surface=surface,
        installation_ref=ref,
        label=label[:80],
        method=method,
        evidence=evidence,
        replaces_id=old.id if old else None,
        authorized_at=now,
    )
    db.add(use)
    if exception is not None:
        exception.used_at = now
    record(
        db,
        actor=user_id,
        action="trial.device_authorized",
        target_type="trial_grant",
        target_id=str(grant.id),
        details={"surface": surface, "method": method, "replaces": str(old.id) if old else None},
    )
    db.commit()
    db.refresh(use)
    return _decision("device_authorized", grant=grant, device=use)


def remove_device(db: Session, user_id: uuid.UUID, device_id: uuid.UUID) -> None:
    use = db.get(TrialDeviceUse, device_id)
    if use is None or use.user_id != user_id or use.status != "authorized":
        raise NotFound("Device not found.")
    use.status = "removed"
    use.removed_at = _now(db)
    record(db, actor=user_id, action="trial.device_removed", target_type="trial_device_use", target_id=str(use.id))
    db.commit()


def grant_exception(
    db: Session, actor: uuid.UUID, user_id: uuid.UUID, *, surface: str, days: int, reason: str
) -> TrialException:
    """§16.7: an authorised reviewer's account-scoped, time-bounded exception. It never clears provider markers or
    resets program history, and it never extends the account's original trial dates."""
    if surface not in ("ios", "android", "web"):
        raise Unprocessable("Unknown surface.")
    if not 1 <= days <= 30:
        raise Unprocessable("An exception lasts 1 to 30 days.")
    now = _now(db)
    exc = TrialException(
        user_id=user_id, surface=surface, reason=reason.strip(), granted_by=actor, expires_at=now + timedelta(days=days)
    )
    db.add(exc)
    record(
        db,
        actor=actor,
        action="trial.exception_granted",
        target_type="app_user",
        target_id=str(user_id),
        details={"surface": surface, "days": days, "reason": reason.strip()},
    )
    db.commit()
    db.refresh(exc)
    return exc


def device_allows(db: Session, user_id: uuid.UUID, *, client: str | None, install_token: str | None) -> str | None:
    """Server-side check for protected trial use on a native device (§16.4: lessons and new attempts). Returns None
    when allowed, else the state to report. Independent access is never blocked. Web requests are not checked here.

    Limit (disclosed): until per-request attestation exists (App Attest / Play Integrity, B07), the client type and
    installation token are asserted by the app, so this is a cooperative gate, not proof of a physical device."""
    if client != "native":
        return None
    now = _now(db)
    if _independent_access(db, user_id, now):
        return None
    grant = _grant(db, user_id)
    if grant is None or grant.status != "active" or grant.ends_at <= now:
        return None  # no trial access to protect here; the entitlement check reports the plan state
    ref = installation_ref(install_token) if install_token else None
    if ref is not None and db.scalar(
        select(TrialDeviceUse.id).where(
            TrialDeviceUse.grant_id == grant.id,
            TrialDeviceUse.installation_ref == ref,
            TrialDeviceUse.status == "authorized",
        )
    ):
        return None
    return "device_authorization_required"


def review_overdue_claims(db: Session) -> int:
    """Move unresolved claims older than the recovery window to REVIEW_REQUIRED (scheduled job)."""
    now = _now(db)
    n = 0
    for c in db.scalars(
        select(TrialClaim)
        .where(
            TrialClaim.status.in_(["PENDING_VERIFICATION", "MARK_PENDING", "MARK_UNKNOWN", "MARK_CONFIRMED"]),
            TrialClaim.created_at < now - RECOVERY_WINDOW,
        )
        .with_for_update(skip_locked=True)
    ):
        _move(db, c, "REVIEW_REQUIRED", "unresolved after the 7-day recovery window", "review_required")
        n += 1
    db.commit()
    return n
