"""Asynchronous reporting exports API (P16.S4.T2; EXPORTS-01). See `service` for the lifecycle and guarantees."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.modules.exports import service
from portal_api.modules.identity.deps import CurrentPrincipal

router = APIRouter(prefix="/v1", tags=["exports"])
DB = Annotated[Session, Depends(get_session)]


class ExportIn(BaseModel):
    kind: Literal["audit_events", "personal_data"]
    params: dict[str, Any] = Field(default_factory=dict)


class ExportOut(BaseModel):
    id: uuid.UUID
    kind: str
    params: dict[str, Any]
    status: Literal["queued", "running", "ready", "failed", "cancelled", "expired"]
    tries: int
    error: str | None
    row_count: int | None
    byte_size: int | None
    downloads: int
    created_at: datetime
    finished_at: datetime | None
    expires_at: datetime | None


def _out(j: service.ExportJob) -> ExportOut:
    return ExportOut(
        id=j.id,
        kind=j.kind,
        params=j.params or {},
        status=j.status,  # type: ignore[arg-type]
        tries=j.tries,
        error=j.error,
        row_count=j.row_count,
        byte_size=j.byte_size,
        downloads=j.downloads,
        created_at=j.created_at,
        finished_at=j.finished_at,
        expires_at=j.expires_at,
    )


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.post(
    "/exports", response_model=ExportOut, status_code=202, summary="Request an export (generated in the background)"
)
def request_export(db: DB, who: CurrentPrincipal, body: ExportIn, response: Response) -> ExportOut:
    _private(response)
    return _out(service.request(db, who, body.kind, body.params))


@router.get("/exports", response_model=list[ExportOut], summary="Your exports, newest first")
def my_exports(db: DB, who: CurrentPrincipal, response: Response) -> list[ExportOut]:
    _private(response)
    return [_out(j) for j in service.mine(db, who)]


@router.get("/exports/{job_id}", response_model=ExportOut, summary="One of your exports")
def get_export(db: DB, who: CurrentPrincipal, job_id: uuid.UUID, response: Response) -> ExportOut:
    _private(response)
    return _out(service.own(db, who, job_id))


@router.post("/exports/{job_id}/cancel", response_model=ExportOut, summary="Cancel a queued or running export")
def cancel_export(db: DB, who: CurrentPrincipal, job_id: uuid.UUID, response: Response) -> ExportOut:
    _private(response)
    return _out(service.cancel(db, who, job_id))


@router.post("/exports/{job_id}/retry", response_model=ExportOut, summary="Retry a failed export")
def retry_export(db: DB, who: CurrentPrincipal, job_id: uuid.UUID, response: Response) -> ExportOut:
    _private(response)
    return _out(service.retry(db, who, job_id))


@router.get("/exports/{job_id}/download", summary="Download a ready export (permission rechecked; audited)")
def download_export(db: DB, who: CurrentPrincipal, job_id: uuid.UUID) -> Response:
    data, media_type, name = service.download(db, who, job_id)
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "private, no-store"},
    )
