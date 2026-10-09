from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

Disposition = Literal["accepted", "stale", "invalid", "late", "finalised", "locked", "conflict"]


class ChapterAvailability(BaseModel):
    chapter_id: uuid.UUID
    number: int
    title: str
    questions: int = Field(description="Approved, published question families available for practice")


class AvailabilityOut(BaseModel):
    grade: int
    subject: str
    chapters: list[ChapterAvailability]


class FormCreateIn(BaseModel):
    grade: Literal[11, 12]
    subject: str = Field(min_length=2, max_length=40)
    chapter_ids: list[uuid.UUID] = Field(min_length=1, max_length=40)
    topic_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    question_count: int = Field(ge=1, le=100)
    timed_minutes: int | None = Field(default=None, ge=1, le=300)
    feedback_mode: Literal["deferred", "immediate"] = "deferred"


class FormOut(BaseModel):
    id: uuid.UUID
    grade: int
    subject: str
    scope: dict[str, Any]
    question_count: int
    duration_s: int | None
    late_write_tolerance_ms: int
    feedback_mode: Literal["deferred", "immediate"]
    negative_marks: int
    created_at: datetime


class OptionSnapshot(BaseModel):
    id: str
    blocks: list[dict[str, Any]]


class ItemSnapshot(BaseModel):
    """What a learner sees during an attempt. Keys and explanations are never part of this payload."""

    position: int
    marks: int
    stem: list[dict[str, Any]]
    options: list[OptionSnapshot]


class AnswerOut(BaseModel):
    position: int
    option_id: str | None
    revision: int
    op_id: uuid.UUID
    saved_at: datetime
    revealed: bool


class ReceiptOut(BaseModel):
    id: uuid.UUID
    reason: Literal["manual", "expiry"]
    admitted_at: datetime
    answered_count: int
    question_count: int
    ledger_hash: str


class AttemptOut(BaseModel):
    id: uuid.UUID
    form_id: uuid.UUID
    status: Literal["active", "finalised", "void"]
    started_at: datetime
    deadline_at: datetime | None = Field(description="D: editing closes")
    cutoff_at: datetime | None = Field(description="C = D + T: the server admits no writes after this")
    tolerance_ms: int = Field(description="T, pinned at start")
    server_now: datetime
    feedback_mode: Literal["deferred", "immediate"]
    items: list[ItemSnapshot]
    answers: list[AnswerOut]
    receipt: ReceiptOut | None


class OpIn(BaseModel):
    op_id: uuid.UUID = Field(description="Client-generated idempotency key for this operation")
    position: int = Field(ge=1, le=200)
    revision: int = Field(ge=1, description="Monotonic per position on the client")
    option_id: str | None = Field(default=None, max_length=12, description="null clears the answer")


class OpsIn(BaseModel):
    ops: list[OpIn] = Field(min_length=1, max_length=50)


class OpResult(BaseModel):
    op_id: uuid.UUID
    position: int
    revision: int
    option_id: str | None
    disposition: Disposition
    admitted_at: datetime
    replay: bool = Field(description="True when this is the stored result of an earlier identical request")


class SaveOut(BaseModel):
    status: Literal["active", "finalised", "void"]
    results: list[OpResult]
    receipt_id: uuid.UUID | None


class SubmitIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=80)
    ops: list[OpIn] = Field(default_factory=list, max_length=50)


class SubmitOut(BaseModel):
    receipt: ReceiptOut
    same_request: bool = Field(description="False when the attempt was finalised by another request or by expiry")
    reconciliation: list[OpResult] = Field(description="Operations presented after finalisation, with their outcome")


class ItemReview(BaseModel):
    position: int
    marks: int
    stem: list[dict[str, Any]]
    options: list[OptionSnapshot]
    chosen: str | None
    correct_option_id: str
    correct: bool | None
    earned: int
    treatment: str
    explanation: dict[str, Any]


class ResultOut(BaseModel):
    attempt_id: uuid.UUID
    version: int
    status: Literal["scored", "not_scorable"]
    raw: int
    maximum: int
    percentage: Decimal | None
    answered: int
    question_count: int
    finalise_reason: Literal["manual", "expiry"]
    items: list[ItemReview]
    revised_at: datetime | None = Field(default=None, description="When this score was revised after review (v2+)")
    revision_reason: str | None = None


class RevealOut(BaseModel):
    position: int
    chosen: str | None
    correct_option_id: str
    correct: bool
    explanation: dict[str, Any]
