from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class WrittenChapter(BaseModel):
    chapter_id: uuid.UUID
    number: int
    title: str
    questions: int = Field(description="Reviewed written questions with a published rubric")


class WrittenAvailabilityOut(BaseModel):
    grade: int
    subject: str
    review_staffed: bool = Field(description="False means no teacher reviewer is available, so nothing is offered")
    upload_allowance_s: int
    caps: dict[str, int]
    chapters: list[WrittenChapter]


class WrittenFormIn(BaseModel):
    grade: Literal[11, 12]
    subject: str = Field(min_length=2, max_length=40)
    chapter_ids: list[uuid.UUID] = Field(min_length=1, max_length=40)
    question_type: Literal["short", "long", "mixed"] = "mixed"
    question_count: int = Field(ge=1, le=10)
    writing_minutes: int | None = Field(default=None, ge=5, le=180, description="None = untimed practice")


class WrittenFormOut(BaseModel):
    id: uuid.UUID
    question_count: int
    max_units: int
    writing_s: int | None
    upload_allowance_s: int
    capture_policy_version: int
    caps: dict[str, int]
    created_at: datetime


class SlotOut(BaseModel):
    key: str
    label: str
    max_units: int


class WrittenItemOut(BaseModel):
    """What the learner sees: the question and its marks. Rubrics are never part of this payload."""

    position: int
    max_units: int
    stem: list[dict[str, Any]]
    subparts: list[dict[str, Any]]
    slots: list[SlotOut]
    answer_language: str


class PageOut(BaseModel):
    """One logical page: a photo, or one page of a PDF. Mapping and the page cap count these."""

    id: uuid.UUID
    file_id: uuid.UUID = Field(description="The uploaded file this page came from")
    page_index: int = Field(description="1-based position within its file")
    file_pages: int = Field(description="How many pages the file has (1 for a photo)")
    size: int = Field(description="Size of the uploaded file in bytes")
    content_type: str = Field(description="Type of the uploaded original; the page itself is served as a PNG preview")
    width: int | None = Field(description="Preview width in pixels")
    height: int | None = Field(description="Preview height in pixels")
    uploaded_at: datetime


class WrittenReceiptOut(BaseModel):
    id: uuid.UUID
    admitted_at: datetime
    manifest_revision: int
    answered_slots: int
    unanswered_slots: int


class WrittenAttemptOut(BaseModel):
    id: uuid.UUID
    form_id: uuid.UUID
    status: Literal["active", "sealed", "expired"]
    started_at: datetime
    writing_deadline_at: datetime | None = Field(description="D: writing should stop (not enforceable at home)")
    upload_cutoff_at: datetime = Field(description="U = D + G: nothing is admitted after this")
    upload_allowance_s: int
    server_now: datetime
    max_units: int
    caps: dict[str, int]
    items: list[WrittenItemOut]
    pages: list[PageOut]
    manifest: dict[str, Any]
    manifest_revision: int
    receipt: WrittenReceiptOut | None


class UploadOut(BaseModel):
    pages: list[PageOut] = Field(description="The logical pages this file added, in order")
    duplicate: bool = Field(description="The same file was already uploaded to this script; it was reused")
    warnings: list[str]


class ManifestIn(BaseModel):
    expected_revision: int = Field(ge=0)
    slots: dict[str, dict[str, Any]] = Field(description='{"1:a": {"pages": [page_id], "unanswered": false}}')


class SealIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=80)
    expected_revision: int = Field(ge=0)


class SealOut(BaseModel):
    receipt: WrittenReceiptOut
    replay: bool
