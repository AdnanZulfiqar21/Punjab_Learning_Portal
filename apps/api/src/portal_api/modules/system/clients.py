"""Client capability manifests and the supported-version policy (roadmap P13.S1.T4, §5.4 rules 3-5; CLIENTS-01).

* **Capability manifests.** Each native build's RendererCapabilityManifest (renderer version, supported block types
  and versions, equation renderer, scientific font set, offline pack format) is registered once per platform and app
  version by an operator (the release step, until a pipeline exists, B03). A registered manifest never changes: a
  different manifest for the same version is refused.
* **Supported versions.** Operators set the minimum supported app version per platform with a reason (MFA,
  audited). Raising it gives notice first: the minimum is announced at once and enforced no sooner than 14 days later
  (§5.4 default). The enforcement moment never falls inside a scheduled mock window: it is refused if chosen inside
  one, and a window scheduled over it later pushes enforcement to that window's close, so nobody is cut off mid-exam.
  Lowering the minimum (a rollback) applies at once.
* **What an app is told.** `GET /v1/clients/policy` answers `ok`, `update_soon` (a minimum it is below is announced:
  with the date) or `update_required`. Once enforced, API requests from a native app below the minimum are refused
  with 426 `UPDATE_REQUIRED`, except the policy itself, runtime configuration, sign-out and health checks; an app that
  doesn't say its version is not judged (builds before this one).
* The web app is deployed by us, so it is always current and has no minimum.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_session
from portal_api.errors import Conflict, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission

PLATFORMS = ("android", "ios")
NOTICE = timedelta(days=14)
VERSION = re.compile(r"^\d{1,4}\.\d{1,4}\.\d{1,4}$")
EXEMPT = ("/v1/clients/policy", "/v1/runtime-config", "/healthz", "/readyz", "/v1/me/session")


def parse(version: str) -> tuple[int, int, int]:
    if not VERSION.match(version):
        raise Unprocessable("Versions look like 1.4.2 (three numbers).")
    a, b, c = (int(x) for x in version.split("."))
    return a, b, c


class ClientVersionPolicy(Base):
    """One decision about a platform's minimum version. Append-only: the newest row is the policy."""

    __tablename__ = "client_version_policy"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(10), index=True)
    min_version: Mapped[str] = mapped_column(String(20))
    notice_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    enforce_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)
    set_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClientManifest(Base):
    __tablename__ = "client_manifest"
    __table_args__ = (UniqueConstraint("platform", "app_version", name="uq_client_manifest"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(10))
    app_version: Mapped[str] = mapped_column(String(20))
    renderer_version: Mapped[int] = mapped_column(Integer)
    pack_format_version: Mapped[int] = mapped_column(Integer)
    block_types: Mapped[dict[str, Any]] = mapped_column(JSONB)
    equation_renderer: Mapped[str | None] = mapped_column(String(40))
    font_set: Mapped[str | None] = mapped_column(String(80))
    registered_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ------------------------------------------------------------------ rules
def _now(db: Session) -> datetime:
    return db.scalar(select(func.now()))  # type: ignore[return-value]


def _window_around(db: Session, at: datetime) -> tuple[datetime, datetime] | None:
    from portal_api.modules.assessment.sessions import MockSession

    row = db.execute(
        select(MockSession.starts_at, MockSession.window_closes_at)
        .where(MockSession.status == "scheduled", MockSession.starts_at <= at, MockSession.window_closes_at > at)
        .order_by(MockSession.window_closes_at.desc())
        .limit(1)
    ).first()
    return (row[0], row[1]) if row else None


def policy(db: Session, platform: str) -> ClientVersionPolicy | None:
    return db.scalar(
        select(ClientVersionPolicy)
        .where(ClientVersionPolicy.platform == platform)
        .order_by(ClientVersionPolicy.created_at.desc(), ClientVersionPolicy.id.desc())
        .limit(1)
    )


def effective_at(db: Session, p: ClientVersionPolicy) -> datetime:
    """When the minimum really applies: its enforcement time, moved to the end of a mock window scheduled over it."""
    window = _window_around(db, p.enforce_at)
    return window[1] if window else p.enforce_at


def status_for(db: Session, platform: str, version: str) -> dict[str, Any]:
    p = policy(db, platform)
    if p is None or parse(version) >= parse(p.min_version):
        return {"status": "ok", "min_version": p.min_version if p else None, "enforce_at": None}
    applies = effective_at(db, p)
    return {
        "status": "update_required" if _now(db) >= applies else "update_soon",
        "min_version": p.min_version,
        "enforce_at": applies,
    }


def set_minimum(
    db: Session, who: Principal, platform: str, min_version: str, reason: str, enforce_at: datetime | None
) -> ClientVersionPolicy:
    if platform not in PLATFORMS:
        raise Unprocessable("Platforms are android and ios; the web app is always current.")
    parse(min_version)
    now = _now(db)
    previous = policy(db, platform)
    raising = previous is None or parse(min_version) > parse(previous.min_version)
    when = enforce_at or (now + NOTICE if raising else now)
    if raising and when < now + NOTICE:
        raise Conflict(
            "Learners get 14 days' notice before an older app stops working. Choose a later date.",
            code_reason="NOTICE_TOO_SHORT",
        )
    window = _window_around(db, when)
    if window is not None:
        raise Conflict(
            f"That moment falls inside a scheduled mock window ({window[0]:%d %b %H:%M} to {window[1]:%d %b %H:%M} "
            "UTC). Choose a time outside it.",
            code_reason="IN_MOCK_WINDOW",
        )
    row = ClientVersionPolicy(
        platform=platform,
        min_version=min_version,
        notice_at=now,
        enforce_at=when,
        reason=reason.strip(),
        set_by=who.user.id,
    )
    db.add(row)
    db.flush()
    record(
        db,
        actor=who.user.id,
        action="client.minimum_set",
        target_type="client_version_policy",
        target_id=platform,
        details={
            "min_version": min_version,
            "previous": previous.min_version if previous else None,
            "enforce_at": when.isoformat(),
            "reason": reason.strip(),
        },
    )
    db.commit()
    _cache.clear()
    return row


def register_manifest(db: Session, who: Principal, body: ClientManifestIn) -> ClientManifest:
    parse(body.app_version)
    existing = db.scalar(
        select(ClientManifest).where(
            ClientManifest.platform == body.platform, ClientManifest.app_version == body.app_version
        )
    )
    fields = body.model_dump(exclude={"platform", "app_version"})
    if existing is not None:
        same = all(getattr(existing, k) == v for k, v in fields.items())
        if not same:
            raise Conflict("This build's manifest is already registered differently; a build never changes.")
        return existing
    m = ClientManifest(platform=body.platform, app_version=body.app_version, registered_by=who.user.id, **fields)
    db.add(m)
    db.flush()
    record(
        db,
        actor=who.user.id,
        action="client.manifest_registered",
        target_type="client_manifest",
        target_id=f"{body.platform}:{body.app_version}",
        details={"renderer_version": body.renderer_version, "pack_format_version": body.pack_format_version},
    )
    db.commit()
    return m


# A request-path check reads the policy at most once a minute per platform.
_cache: dict[str, tuple[float, tuple[str, datetime] | None]] = {}


def enforced_minimum(db: Session, platform: str) -> tuple[str, datetime] | None:
    hit = _cache.get(platform)
    if hit is not None and time.monotonic() - hit[0] < 60:
        return hit[1]
    p = policy(db, platform)
    value = (p.min_version, effective_at(db, p)) if p is not None else None
    _cache[platform] = (time.monotonic(), value)
    return value


def refuses(db: Session, path: str, platform: str | None, version: str | None) -> dict[str, Any] | None:
    """For the request middleware: the problem body when this native app version may no longer use the API."""
    if not platform or platform not in PLATFORMS or not version or not VERSION.match(version):
        return None
    if path.startswith(EXEMPT) or not path.startswith("/v1/"):
        return None
    minimum = enforced_minimum(db, platform)
    if minimum is None or parse(version) >= parse(minimum[0]) or datetime.now(minimum[1].tzinfo) < minimum[1]:
        return None
    return {"min_version": minimum[0]}


# ------------------------------------------------------------------ routes
router = APIRouter(prefix="/v1", tags=["clients"])
DB = Annotated[Session, Depends(get_session)]
Operator = Annotated[Principal, Depends(require(Permission.operate_platform))]


class ClientPolicyOut(BaseModel):
    status: Literal["ok", "update_soon", "update_required"]
    min_version: str | None
    enforce_at: datetime | None = Field(description="When this app version stops working (for update_soon/required)")


class ClientMinimumIn(BaseModel):
    min_version: str = Field(min_length=5, max_length=20)
    reason: str = Field(min_length=10, max_length=1000)
    enforce_at: datetime | None = Field(default=None, description="Defaults to 14 days from now when raising")


class ClientManifestIn(BaseModel):
    platform: Literal["android", "ios"]
    app_version: str = Field(min_length=5, max_length=20)
    renderer_version: int = Field(ge=1, le=100)
    pack_format_version: int = Field(ge=1, le=100)
    block_types: dict[str, int] = Field(description="Supported block type -> highest version")
    equation_renderer: str | None = Field(default=None, max_length=40)
    font_set: str | None = Field(default=None, max_length=80)


class ClientPlatformState(BaseModel):
    platform: str
    min_version: str | None
    notice_at: datetime | None
    enforce_at: datetime | None
    reason: str | None
    manifests: list[ClientManifestIn]


@router.get("/clients/policy", response_model=ClientPolicyOut, summary="Whether this app version is supported (public)")
def client_policy(
    db: DB,
    response: Response,
    platform: Annotated[Literal["android", "ios"], Query()],
    version: Annotated[str, Query(min_length=5, max_length=20)],
) -> ClientPolicyOut:
    response.headers["Cache-Control"] = "public, max-age=300"
    return ClientPolicyOut(**status_for(db, platform, version))


@router.get("/ops/clients", response_model=list[ClientPlatformState], summary="Supported versions and build manifests")
def ops_clients(db: DB, who: Operator, response: Response) -> list[ClientPlatformState]:
    response.headers["Cache-Control"] = "private, no-store"
    out = []
    for platform in PLATFORMS:
        p = policy(db, platform)
        manifests = db.scalars(
            select(ClientManifest).where(ClientManifest.platform == platform).order_by(ClientManifest.registered_at)
        )
        out.append(
            ClientPlatformState(
                platform=platform,
                min_version=p.min_version if p else None,
                notice_at=p.notice_at if p else None,
                enforce_at=effective_at(db, p) if p else None,
                reason=p.reason if p else None,
                manifests=[
                    ClientManifestIn(
                        platform=m.platform,  # type: ignore[arg-type]
                        app_version=m.app_version,
                        renderer_version=m.renderer_version,
                        pack_format_version=m.pack_format_version,
                        block_types=m.block_types,
                        equation_renderer=m.equation_renderer,
                        font_set=m.font_set,
                    )
                    for m in manifests
                ],
            )
        )
    return out


@router.put(
    "/ops/clients/{platform}/minimum",
    response_model=list[ClientPlatformState],
    summary="Set the minimum supported app version (operators, MFA, audited; 14 days' notice when raising)",
)
def ops_set_minimum(
    db: DB, who: Operator, platform: str, body: ClientMinimumIn, response: Response
) -> list[ClientPlatformState]:
    set_minimum(db, who, platform, body.min_version, body.reason, body.enforce_at)
    return ops_clients(db, who, response)


@router.post(
    "/ops/clients/manifests",
    response_model=ClientManifestIn,
    status_code=201,
    summary="Register a build's renderer capability manifest (operators; once per build)",
)
def ops_register_manifest(db: DB, who: Operator, body: ClientManifestIn, response: Response) -> ClientManifestIn:
    response.headers["Cache-Control"] = "private, no-store"
    register_manifest(db, who, body)
    return body
