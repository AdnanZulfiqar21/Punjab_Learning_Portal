"""Learner written-practice API (W03/W04). All responses are private and uncached."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from portal_api.db import get_session
from portal_api.errors import NotFound, TooLarge
from portal_api.modules.access import service as access
from portal_api.modules.content import written as wq
from portal_api.modules.content.models import ContentVersion
from portal_api.modules.identity.deps import CurrentPrincipal
from portal_api.modules.system import operations
from portal_api.modules.written import evidence, linked, service
from portal_api.modules.written.models import WrittenAttempt, WrittenFile, WrittenForm, WrittenPage, WrittenReceipt
from portal_api.modules.written.schemas import (
    LinkedFormIn,
    LinkedFormOut,
    LinkedFromOut,
    ManifestIn,
    PageOut,
    SealIn,
    SealOut,
    SlotOut,
    UploadOut,
    WrittenAttemptOut,
    WrittenAvailabilityOut,
    WrittenChapter,
    WrittenFormIn,
    WrittenFormOut,
    WrittenItemOut,
    WrittenReceiptOut,
)

router = APIRouter(prefix="/v1", tags=["written practice"])
DB = Annotated[Session, Depends(get_session)]
UPLOAD_LIMIT = max(evidence.IMAGE_MAX_BYTES, evidence.PDF_MAX_BYTES)


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def page_out(p: WrittenPage, f: WrittenFile) -> PageOut:
    return PageOut(
        id=p.id,
        file_id=f.id,
        page_index=p.page_index,
        file_pages=f.page_count,
        size=f.size,
        content_type=f.content_type,
        width=p.width,
        height=p.height,
        uploaded_at=p.uploaded_at,
    )


def pages_out(db: Session, pages: list[WrittenPage]) -> list[PageOut]:
    files = {f.id: f for f in db.scalars(select(WrittenFile).where(WrittenFile.id.in_({p.file_id for p in pages})))}
    return [page_out(p, files[p.file_id]) for p in pages]


def _receipt_out(r: WrittenReceipt) -> WrittenReceiptOut:
    return WrittenReceiptOut(
        id=r.id,
        admitted_at=r.admitted_at,
        manifest_revision=r.manifest_revision,
        answered_slots=r.answered_slots,
        unanswered_slots=r.unanswered_slots,
    )


def _attempt_out(db: Session, a: WrittenAttempt) -> WrittenAttemptOut:
    form = db.get(WrittenForm, a.form_id)
    assert form is not None
    items = []
    for fi in form.items:
        qv = db.get(ContentVersion, fi.question_version_id)
        assert qv is not None
        q, _ = wq.parse_written(qv.body)
        assert q is not None
        labels = {s.id: s.label for s in q.subparts}
        maxima = wq.subpart_maxima(q)
        items.append(
            WrittenItemOut(
                position=fi.position,
                max_units=fi.max_units,
                stem=qv.body.get("stem", []),
                subparts=[
                    {
                        "id": s.id,
                        "label": s.label,
                        "blocks": s.model_dump(mode="json")["blocks"],
                        "max_units": s.max_units,
                    }
                    for s in q.subparts
                ],
                slots=[
                    SlotOut(
                        key=service.slot_key(fi.position, sid),
                        label=f"Question {fi.position} {labels[sid]}" if sid else f"Question {fi.position}",
                        max_units=m,
                    )
                    for sid, m in maxima.items()
                ],
                answer_language=q.answer_language,
            )
        )
    receipt = service.receipt_for(db, a.id)
    return WrittenAttemptOut(
        id=a.id,
        form_id=a.form_id,
        linked_from=_linked_from(form),
        status=a.status,  # type: ignore[arg-type]
        started_at=a.started_at,
        writing_deadline_at=a.writing_deadline_at,
        upload_cutoff_at=a.upload_cutoff_at,
        upload_allowance_s=a.upload_allowance_s,
        server_now=service.db_now(db),
        max_units=form.max_units,
        caps=form.caps,
        items=items,
        pages=pages_out(db, service.pages_of(db, a.id)),
        manifest=a.manifest,
        manifest_revision=a.manifest_revision,
        receipt=_receipt_out(receipt) if receipt else None,
    )


def _linked_from(form: WrittenForm) -> LinkedFromOut | None:
    if form.linked_from_attempt_id is None:
        return None
    return LinkedFromOut(
        attempt_id=form.linked_from_attempt_id,
        reason=form.link_reason,  # type: ignore[arg-type]
        positions=form.link_positions or [],
    )


def _linked_form_out(db: Session, who: CurrentPrincipal, form: WrittenForm) -> LinkedFormOut:
    started = db.scalar(select(WrittenAttempt.id).where(WrittenAttempt.form_id == form.id))
    linked_from = _linked_from(form)
    assert linked_from is not None
    return LinkedFormOut(
        form_id=form.id,
        question_count=len(form.items),
        max_units=form.max_units,
        allowance_units=linked.allowance_units(db, form),
        allowance_available=access.allowance(db, who.user.id)["available"],
        linked_from=linked_from,
        started_attempt_id=started,
    )


@router.post(
    "/written-attempts/{attempt_id}/linked-forms",
    response_model=LinkedFormOut,
    status_code=201,
    summary="Prepare a new practice test linked to this one (W04.S3.T3); starting it uses allowance like any test",
)
def create_linked_form(
    db: DB,
    who: CurrentPrincipal,
    attempt_id: uuid.UUID,
    body: LinkedFormIn,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=80)],
) -> LinkedFormOut:
    _private(response)
    form = linked.create_linked_form(
        db,
        who,
        attempt_id,
        reason=body.reason,
        positions=body.positions,
        revision_id=body.revision_id,
        idempotency_key=idempotency_key,
    )
    return _linked_form_out(db, who, form)


@router.get("/written/linked-forms/{form_id}", response_model=LinkedFormOut)
def get_linked_form(db: DB, who: CurrentPrincipal, form_id: uuid.UUID, response: Response) -> LinkedFormOut:
    _private(response)
    form = db.get(WrittenForm, form_id)
    if form is None or form.owner_id != who.user.id or form.linked_from_attempt_id is None:
        raise NotFound("Test not found.")
    return _linked_form_out(db, who, form)


@router.get("/written/availability", response_model=WrittenAvailabilityOut)
def availability(
    db: DB,
    _: CurrentPrincipal,
    response: Response,
    grade: Annotated[int, Query(ge=11, le=12)],
    subject: Annotated[str, Query(min_length=2, max_length=40)],
) -> WrittenAvailabilityOut:
    _private(response)
    out = service.availability(db, grade, subject)
    return WrittenAvailabilityOut(
        grade=grade,
        subject=subject,
        review_staffed=out["review_staffed"],
        review_accepting=out["review_accepting"],
        upload_allowance_s=out["upload_allowance_s"],
        caps=out["caps"],
        chapters=[WrittenChapter(**c) for c in out["chapters"]],
    )


@router.post(
    "/written/forms",
    response_model=WrittenFormOut,
    status_code=201,
    dependencies=[Depends(operations.requires("new_written_tests"))],
)
def create_form(
    db: DB,
    who: CurrentPrincipal,
    body: WrittenFormIn,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=80)],
) -> WrittenFormOut:
    _private(response)
    f = service.create_form(
        db,
        who,
        idempotency_key=idempotency_key,
        grade=body.grade,
        subject=body.subject,
        chapter_ids=body.chapter_ids,
        question_type=body.question_type,
        question_count=body.question_count,
        writing_minutes=body.writing_minutes,
    )
    return WrittenFormOut(
        id=f.id,
        question_count=len(f.items),
        max_units=f.max_units,
        writing_s=f.writing_s,
        upload_allowance_s=f.upload_allowance_s,
        capture_policy_version=f.capture_policy_version,
        caps=f.caps,
        created_at=f.created_at,
    )


@router.post("/written/forms/{form_id}/attempt", response_model=WrittenAttemptOut)
def start(db: DB, who: CurrentPrincipal, form_id: uuid.UUID, response: Response) -> WrittenAttemptOut:
    _private(response)
    attempt = service.start(db, who, form_id)
    return _attempt_out(db, service.load(db, who, attempt.id))


@router.get("/written-attempts/{attempt_id}", response_model=WrittenAttemptOut)
def get_attempt(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, response: Response) -> WrittenAttemptOut:
    _private(response)
    return _attempt_out(db, service.load(db, who, attempt_id))


@router.post(
    "/written-attempts/{attempt_id}/pages",
    response_model=UploadOut,
    status_code=201,
    summary="Upload one file (raw JPEG, PNG or PDF body); it is validated in an isolated worker",
)
async def upload(
    db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, request: Request, response: Response
) -> UploadOut:
    _private(response)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > UPLOAD_LIMIT:
        raise TooLarge("This file is larger than any accepted page.")
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > UPLOAD_LIMIT:
            raise TooLarge("This file is larger than any accepted page.")
    file, pages, duplicate, warnings = await run_in_threadpool(service.upload_page, db, who, attempt_id, bytes(buf))
    return UploadOut(pages=[page_out(p, file) for p in pages], duplicate=duplicate, warnings=warnings)


@router.get(
    "/written-attempts/{attempt_id}/pages/{page_id}",
    summary="Your own page as its validated PNG preview (private; originals are never served)",
)
def get_page(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, page_id: uuid.UUID) -> Response:
    data, content_type = service.page_bytes(db, who, attempt_id, page_id)
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


@router.put("/written-attempts/{attempt_id}/manifest", response_model=WrittenAttemptOut)
def put_manifest(
    db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, body: ManifestIn, response: Response
) -> WrittenAttemptOut:
    _private(response)
    attempt = service.update_manifest(db, who, attempt_id, expected_revision=body.expected_revision, slots=body.slots)
    return _attempt_out(db, attempt)


@router.post(
    "/written-attempts/{attempt_id}/seal", response_model=SealOut, summary="Submit the answer script (§20.7.2)"
)
def seal(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, body: SealIn, response: Response) -> SealOut:
    _private(response)
    receipt, replay = service.seal(
        db, who, attempt_id, idempotency_key=body.idempotency_key, expected_revision=body.expected_revision
    )
    return SealOut(receipt=_receipt_out(receipt), replay=replay)
