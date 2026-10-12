"""Sellable products (roadmap P14.S1.T1, PRODUCTS-01).

A **product** is what a learner can buy: the whole platform, a subject package, an exam package or a bundle. Its
definition (kind, scope, duration, disclosed written allowance) is kept apart from its **prices** and the **sales
channel**, so a price change never rewrites what was sold, and an entitlement keeps the scope it was granted with.

* Lifecycle: `draft` (editable) → `active` (on sale; the definition is frozen) → `retired` (no longer sold). Retiring
  never touches entitlements already granted. To change what an active product contains, retire it and define a new
  one.
* Scope is checked against the live catalogue: grades 11 and 12 only, subjects that have a book in that grade, and
  exam codes that have an exam profile. Class XI and XII stay distinct (a package names its grades).
* Prices are append-only versions in integer minor units with an ISO 4217 currency code, per channel. Today the only
  channel is `web` (decision D02 default: fixed-duration one-time purchases on the web; store subscriptions wait on
  D04). The current price is the latest version that has started; a version can withdraw the product from sale.
* The one platform trial (`PLATFORM_TRIAL_30D`) is not a product and can't be defined as one: there is no second,
  per-module trial, and switching subjects never restarts trial eligibility (§16).
* Nothing here invents a price or a product: the catalogue starts empty, and finance staff (MFA, audited) define it.
  Package-scoped access checks are P14.S1.T2; until then a package can be defined and priced but not granted.

**Purchase terms** (P14.S1.T3, PRICING-01): what a buyer is told before paying (taxes, renewal, the early-conversion
rule of §16.9 T5, refunds) is owner-reviewed text, never written by the code. Finance staff draft a version and a
*different* finance person publishes it; publishing supersedes the previous version, and every version is kept. The
public pricing page shows the published version, or says plainly that terms aren't published yet.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_session
from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission

KINDS = ("platform", "subject_package", "exam_package", "bundle")
STATUSES = ("draft", "active", "retired")
CHANNELS = ("web",)  # D02 default; store channels wait on D04
CODE = re.compile(r"^[a-z][a-z0-9-]{2,39}$")


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (
        CheckConstraint(f"kind in ({', '.join(repr(k) for k in KINDS)})", name="product_kind"),
        CheckConstraint(f"status in ({', '.join(repr(s) for s in STATUSES)})", name="product_status"),
        CheckConstraint("duration_days between 1 and 366", name="product_duration"),
        CheckConstraint("written_units >= 0", name="product_written_units"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16))
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # {grades, subjects, exams}; {} = everything
    duration_days: Mapped[int] = mapped_column(SmallInteger)
    written_units: Mapped[int] = mapped_column(Integer, default=0)  # the disclosed, finite written allowance
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(8), default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductPrice(Base):
    """One price version for one channel. Append-only: a new version supersedes, nothing is edited or deleted."""

    __tablename__ = "product_price"
    __table_args__ = (
        CheckConstraint(f"channel in ({', '.join(repr(c) for c in CHANNELS)})", name="product_price_channel"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="product_price_currency"),
        CheckConstraint("amount_minor is null or amount_minor >= 0", name="product_price_amount"),
        CheckConstraint("(on_sale and amount_minor is not null) or not on_sale", name="product_price_on_sale"),
        Index("ix_product_price_current", "product_id", "channel", "starts_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"))
    channel: Mapped[str] = mapped_column(String(8))
    currency: Mapped[str] = mapped_column(String(3))
    amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    on_sale: Mapped[bool] = mapped_column(Boolean)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)
    set_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


TERMS_STATUSES = ("draft", "published", "superseded")


class CommerceTerms(Base):
    __tablename__ = "commerce_terms"
    __table_args__ = (
        CheckConstraint(f"status in ({', '.join(repr(t) for t in TERMS_STATUSES)})", name="commerce_terms_status"),
        CheckConstraint("published_by is null or published_by <> drafted_by", name="commerce_terms_two_people"),
        Index("uq_commerce_terms_published", "status", unique=True, postgresql_where=text("status = 'published'")),
        Index("uq_commerce_terms_draft", "status", unique=True, postgresql_where=text("status = 'draft'")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    tax_note: Mapped[str] = mapped_column(Text)
    renewal_note: Mapped[str] = mapped_column(Text)
    conversion_note: Mapped[str] = mapped_column(Text)
    refund_note: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="draft")
    drafted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    drafted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ------------------------------------------------------------------ rules
def _now(db: Session) -> datetime:
    return db.scalar(select(func.now()))  # type: ignore[return-value]


def _catalogue(db: Session) -> tuple[set[tuple[int, str]], set[str]]:
    from portal_api.modules.assessment.profiles import ExamProfile
    from portal_api.modules.curriculum.models import BookEdition, Grade, Subject

    books = {
        (int(g), str(s))
        for g, s in db.execute(
            select(Grade.number, Subject.code)
            .join(BookEdition, BookEdition.grade_id == Grade.id)
            .join(Subject, BookEdition.subject_id == Subject.id)
        )
    }
    exams = {str(c) for c in db.scalars(select(ExamProfile.code))}
    return books, exams


def normalise_scope(db: Session, kind: str, scope: dict[str, Any]) -> dict[str, Any]:
    grades = sorted({int(g) for g in scope.get("grades") or []})
    subjects = sorted({str(s) for s in scope.get("subjects") or []})
    exams = sorted({str(e) for e in scope.get("exams") or []})
    if kind == "platform":
        if grades or subjects or exams:
            raise Unprocessable("The platform product covers everything in the active scope; leave its scope empty.")
        return {}
    books, known_exams = _catalogue(db)
    if any(g not in (11, 12) for g in grades):
        raise Unprocessable("Grades are 11 and 12 only.")
    if subjects and not grades:
        raise Unprocessable("Name the class (11, 12 or both) for each subject package.")
    missing = [f"Class {g} {s}" for g in grades for s in subjects if (g, s) not in books]
    if missing:
        raise Unprocessable(f"There is no book for: {', '.join(missing)}.")
    unknown = [e for e in exams if e not in known_exams]
    if unknown:
        raise Unprocessable(f"Unknown exam profile: {', '.join(unknown)}.")
    if kind == "subject_package" and (not subjects or exams):
        raise Unprocessable("A subject package names its subjects and classes, and no exams.")
    if kind == "exam_package" and (not exams or subjects or grades):
        raise Unprocessable("An exam package names its exam profiles only.")
    if kind == "bundle" and len(subjects) + len(exams) < 2:
        raise Unprocessable("A bundle combines at least two subjects or exams.")
    return {"grades": grades, "subjects": subjects, "exams": exams}


def _get(db: Session, product_id: uuid.UUID, lock: bool = False) -> Product:
    stmt = select(Product).where(Product.id == product_id)
    p = db.scalar(stmt.with_for_update() if lock else stmt)
    if p is None:
        raise NotFound("Product not found.")
    return p


def _audit(db: Session, who: Principal, action: str, p: Product, **details: Any) -> None:
    record(db, actor=who.user.id, action=action, target_type="product", target_id=str(p.id), details=details)


def create(db: Session, who: Principal, body: ProductIn) -> Product:
    if not CODE.match(body.code):
        raise Unprocessable("Codes are 3 to 40 lowercase letters, digits or hyphens, starting with a letter.")
    if body.code in ("trial", "platform-trial") or "trial" in body.code.split("-"):
        raise Unprocessable("The free trial is one platform programme, not a product.", code_reason="TRIAL_NOT_PRODUCT")
    if db.scalar(select(Product.id).where(Product.code == body.code)) is not None:
        raise Conflict("A product with this code already exists.", code_reason="PRODUCT_CODE_TAKEN")
    p = Product(
        code=body.code,
        name=body.name.strip(),
        kind=body.kind,
        scope=normalise_scope(db, body.kind, body.scope.model_dump()),
        duration_days=body.duration_days,
        written_units=body.written_units,
        description=body.description.strip(),
        created_by=who.user.id,
    )
    db.add(p)
    db.flush()
    _audit(db, who, "product.created", p, kind=p.kind, scope=p.scope)
    db.commit()
    return p


def update(db: Session, who: Principal, product_id: uuid.UUID, body: ProductIn) -> Product:
    p = _get(db, product_id, lock=True)
    if p.status != "draft":
        raise Conflict(
            "An active or retired product can't be changed. Retire it and define a new one.",
            code_reason="PRODUCT_FROZEN",
        )
    if body.code != p.code:
        raise Unprocessable("A product's code can't be changed.")
    p.name, p.kind, p.description = body.name.strip(), body.kind, body.description.strip()
    p.scope = normalise_scope(db, body.kind, body.scope.model_dump())
    p.duration_days, p.written_units = body.duration_days, body.written_units
    p.updated_at = _now(db)
    _audit(db, who, "product.updated", p, kind=p.kind, scope=p.scope)
    db.commit()
    return p


def transition(
    db: Session, who: Principal, product_id: uuid.UUID, to: Literal["active", "retired"], reason: str
) -> Product:
    p = _get(db, product_id, lock=True)
    allowed = {"active": ("draft",), "retired": ("draft", "active")}[to]
    if p.status not in allowed:
        raise Conflict(f"A {p.status} product can't become {to}.", code_reason="PRODUCT_STATE")
    now = _now(db)
    p.status = to
    if to == "active":
        p.activated_at = now
    else:
        p.retired_at = now
    p.updated_at = now
    _audit(db, who, f"product.{'activated' if to == 'active' else 'retired'}", p, reason=reason.strip())
    db.commit()
    return p


def set_price(db: Session, who: Principal, product_id: uuid.UUID, body: PriceIn) -> ProductPrice:
    p = _get(db, product_id, lock=True)
    if p.status == "retired":
        raise Conflict("A retired product isn't sold; define a new one.", code_reason="PRODUCT_STATE")
    if body.on_sale and body.amount_minor is None:
        raise Unprocessable("A price on sale needs an amount.")
    now = _now(db)
    price = ProductPrice(
        product_id=p.id,
        channel=body.channel,
        currency=body.currency,
        amount_minor=body.amount_minor,
        on_sale=body.on_sale,
        starts_at=body.starts_at or now,
        reason=body.reason.strip(),
        set_by=who.user.id,
    )
    if price.starts_at < now:
        raise Unprocessable("A price can't start in the past; history is never rewritten.")
    db.add(price)
    db.flush()
    _audit(
        db,
        who,
        "product.price_set",
        p,
        channel=price.channel,
        currency=price.currency,
        amount_minor=price.amount_minor,
        on_sale=price.on_sale,
        starts_at=price.starts_at.isoformat(),
        reason=price.reason,
    )
    db.commit()
    return price


def prices(db: Session, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[ProductPrice]]:
    out: dict[uuid.UUID, list[ProductPrice]] = {i: [] for i in product_ids}
    if product_ids:
        rows = db.scalars(
            select(ProductPrice)
            .where(ProductPrice.product_id.in_(product_ids))
            .order_by(ProductPrice.starts_at, ProductPrice.created_at)
        )
        for row in rows:
            out[row.product_id].append(row)
    return out


def current(history: list[ProductPrice], channel: str, now: datetime) -> ProductPrice | None:
    started = [p for p in history if p.channel == channel and p.starts_at <= now]
    return started[-1] if started else None


def save_terms(db: Session, who: Principal, body: TermsIn) -> CommerceTerms:
    """Create the one open draft, or change it (only its author can)."""
    draft = db.scalar(select(CommerceTerms).where(CommerceTerms.status == "draft").with_for_update())
    if draft is None:
        number = (db.scalar(select(func.max(CommerceTerms.version))) or 0) + 1
        draft = CommerceTerms(version=number, drafted_by=who.user.id)
        db.add(draft)
    elif draft.drafted_by != who.user.id:
        raise Conflict("Another person's draft is open; they can change it, or someone else can publish it.")
    draft.tax_note, draft.renewal_note = body.tax_note.strip(), body.renewal_note.strip()
    draft.conversion_note, draft.refund_note = body.conversion_note.strip(), body.refund_note.strip()
    db.flush()
    record(
        db,
        actor=who.user.id,
        action="commerce_terms.drafted",
        target_type="commerce_terms",
        target_id=str(draft.id),
        details={"version": draft.version},
    )
    db.commit()
    return draft


def publish_terms(db: Session, who: Principal, reason: str) -> CommerceTerms:
    draft = db.scalar(select(CommerceTerms).where(CommerceTerms.status == "draft").with_for_update())
    if draft is None:
        raise NotFound("There is no draft to publish.")
    if draft.drafted_by == who.user.id:
        raise Conflict("A different person must publish the terms you drafted.", code_reason="TWO_PEOPLE")
    now = _now(db)
    for old in db.scalars(select(CommerceTerms).where(CommerceTerms.status == "published").with_for_update()):
        old.status = "superseded"
    db.flush()
    draft.status, draft.published_by, draft.published_at = "published", who.user.id, now
    record(
        db,
        actor=who.user.id,
        action="commerce_terms.published",
        target_type="commerce_terms",
        target_id=str(draft.id),
        details={"version": draft.version, "reason": reason.strip()},
    )
    db.commit()
    return draft


# ------------------------------------------------------------------ schemas
class ScopeIn(BaseModel):
    grades: list[int] = Field(default_factory=list, max_length=2)
    subjects: list[str] = Field(default_factory=list, max_length=10)
    exams: list[str] = Field(default_factory=list, max_length=10)


class ProductIn(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    name: str = Field(min_length=3, max_length=120)
    kind: Literal["platform", "subject_package", "exam_package", "bundle"]
    scope: ScopeIn = Field(default_factory=ScopeIn)
    duration_days: int = Field(ge=1, le=366)
    written_units: int = Field(ge=0, le=500)
    description: str = Field(default="", max_length=2000)


class TransitionIn(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


class PriceIn(BaseModel):
    channel: Literal["web"] = "web"
    currency: str = Field(pattern=r"^[A-Z]{3}$", description="ISO 4217 code, e.g. PKR")
    amount_minor: int | None = Field(default=None, ge=0, description="Integer minor units (paisa for PKR)")
    on_sale: bool = True
    starts_at: datetime | None = Field(default=None, description="Defaults to now; never in the past")
    reason: str = Field(min_length=10, max_length=1000)


class PriceOut(BaseModel):
    channel: str
    currency: str
    amount_minor: int | None
    on_sale: bool
    starts_at: datetime
    reason: str | None = None


class TermsIn(BaseModel):
    tax_note: str = Field(min_length=10, max_length=2000, description="How tax is treated in the prices shown")
    renewal_note: str = Field(min_length=10, max_length=2000, description="Whether and how a plan renews")
    conversion_note: str = Field(min_length=10, max_length=2000, description="Buying during the free trial (§16.9 T5)")
    refund_note: str = Field(min_length=10, max_length=2000, description="Refunds and what they reverse")


class TermsOut(BaseModel):
    version: int
    status: str
    tax_note: str
    renewal_note: str
    conversion_note: str
    refund_note: str
    published_at: datetime | None


class TermsState(BaseModel):
    published: TermsOut | None
    draft: TermsOut | None = None
    draft_is_mine: bool = False


def _terms_out(t: CommerceTerms | None) -> TermsOut | None:
    if t is None:
        return None
    return TermsOut(
        version=t.version,
        status=t.status,
        tax_note=t.tax_note,
        renewal_note=t.renewal_note,
        conversion_note=t.conversion_note,
        refund_note=t.refund_note,
        published_at=t.published_at,
    )


class ProductAdminOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    kind: str
    scope: dict[str, Any]
    duration_days: int
    written_units: int
    description: str
    status: str
    activated_at: datetime | None
    retired_at: datetime | None
    current_price: PriceOut | None
    price_history: list[PriceOut]


class ProductOut(BaseModel):
    """What the public listing shows: the definition and the price on sale now (if any). No staff fields."""

    code: str
    name: str
    kind: str
    scope: dict[str, Any]
    duration_days: int
    written_units: int = Field(description="The disclosed, finite written allowance for the period")
    description: str
    price: PriceOut | None = Field(description="The web price on sale now; null if not priced yet")


def _price_out(p: ProductPrice | None, with_reason: bool) -> PriceOut | None:
    if p is None:
        return None
    return PriceOut(
        channel=p.channel,
        currency=p.currency,
        amount_minor=p.amount_minor,
        on_sale=p.on_sale,
        starts_at=p.starts_at,
        reason=p.reason if with_reason else None,
    )


def _admin_out(db: Session, items: list[Product]) -> list[ProductAdminOut]:
    now = _now(db)
    hist = prices(db, [p.id for p in items])
    return [
        ProductAdminOut(
            id=p.id,
            code=p.code,
            name=p.name,
            kind=p.kind,
            scope=p.scope,
            duration_days=p.duration_days,
            written_units=p.written_units,
            description=p.description,
            status=p.status,
            activated_at=p.activated_at,
            retired_at=p.retired_at,
            current_price=_price_out(current(hist[p.id], "web", now), True),
            price_history=[x for x in (_price_out(h, True) for h in hist[p.id]) if x is not None],
        )
        for p in items
    ]


# ------------------------------------------------------------------ routes
router = APIRouter(prefix="/v1", tags=["products"])
DB = Annotated[Session, Depends(get_session)]
Finance = Annotated[Principal, Depends(require(Permission.finance_operations))]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get("/products", response_model=list[ProductOut], summary="Products on sale and their current web price")
def public_products(db: DB, response: Response) -> list[ProductOut]:
    response.headers["Cache-Control"] = "public, max-age=60"
    items = list(db.scalars(select(Product).where(Product.status == "active").order_by(Product.kind, Product.name)))
    now = _now(db)
    hist = prices(db, [p.id for p in items])
    out = []
    for p in items:
        price = current(hist[p.id], "web", now)
        out.append(
            ProductOut(
                code=p.code,
                name=p.name,
                kind=p.kind,
                scope=p.scope,
                duration_days=p.duration_days,
                written_units=p.written_units,
                description=p.description,
                price=_price_out(price, False) if price is not None and price.on_sale else None,
            )
        )
    return out


@router.get("/admin/products", response_model=list[ProductAdminOut], summary="All products, drafts included (finance)")
def admin_products(db: DB, who: Finance, response: Response) -> list[ProductAdminOut]:
    _private(response)
    return _admin_out(db, list(db.scalars(select(Product).order_by(Product.status, Product.name))))


@router.post("/admin/products", response_model=ProductAdminOut, status_code=201, summary="Define a draft product")
def admin_create(db: DB, who: Finance, body: ProductIn, response: Response) -> ProductAdminOut:
    _private(response)
    return _admin_out(db, [create(db, who, body)])[0]


@router.put("/admin/products/{product_id}", response_model=ProductAdminOut, summary="Change a draft product")
def admin_update(db: DB, who: Finance, product_id: uuid.UUID, body: ProductIn, response: Response) -> ProductAdminOut:
    _private(response)
    return _admin_out(db, [update(db, who, product_id, body)])[0]


@router.post("/admin/products/{product_id}/activate", response_model=ProductAdminOut, summary="Put a product on sale")
def admin_activate(
    db: DB, who: Finance, product_id: uuid.UUID, body: TransitionIn, response: Response
) -> ProductAdminOut:
    _private(response)
    return _admin_out(db, [transition(db, who, product_id, "active", body.reason)])[0]


@router.post("/admin/products/{product_id}/retire", response_model=ProductAdminOut, summary="Stop selling a product")
def admin_retire(
    db: DB, who: Finance, product_id: uuid.UUID, body: TransitionIn, response: Response
) -> ProductAdminOut:
    _private(response)
    return _admin_out(db, [transition(db, who, product_id, "retired", body.reason)])[0]


@router.post(
    "/admin/products/{product_id}/prices",
    response_model=ProductAdminOut,
    status_code=201,
    summary="Add a price version (append-only, integer minor units)",
)
def admin_price(db: DB, who: Finance, product_id: uuid.UUID, body: PriceIn, response: Response) -> ProductAdminOut:
    _private(response)
    set_price(db, who, product_id, body)
    return _admin_out(db, [_get(db, product_id)])[0]


@router.get("/commerce-terms", response_model=TermsState, summary="The published purchase terms (public)")
def public_terms(db: DB, response: Response) -> TermsState:
    response.headers["Cache-Control"] = "public, max-age=60"
    published = db.scalar(select(CommerceTerms).where(CommerceTerms.status == "published"))
    return TermsState(published=_terms_out(published))


@router.get("/admin/commerce-terms", response_model=TermsState, summary="Published and draft purchase terms (finance)")
def admin_terms(db: DB, who: Finance, response: Response) -> TermsState:
    _private(response)
    published = db.scalar(select(CommerceTerms).where(CommerceTerms.status == "published"))
    draft = db.scalar(select(CommerceTerms).where(CommerceTerms.status == "draft"))
    return TermsState(
        published=_terms_out(published),
        draft=_terms_out(draft),
        draft_is_mine=draft is not None and draft.drafted_by == who.user.id,
    )


@router.put("/admin/commerce-terms/draft", response_model=TermsState, summary="Write the draft purchase terms")
def admin_save_terms(db: DB, who: Finance, body: TermsIn, response: Response) -> TermsState:
    save_terms(db, who, body)
    return admin_terms(db, who, response)


@router.post(
    "/admin/commerce-terms/publish",
    response_model=TermsState,
    summary="Publish the draft terms (a different finance person; audited)",
)
def admin_publish_terms(db: DB, who: Finance, body: TransitionIn, response: Response) -> TermsState:
    publish_terms(db, who, body.reason)
    return admin_terms(db, who, response)
