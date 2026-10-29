from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

Disposition = Literal["accepted", "stale", "invalid", "late", "finalised", "locked", "conflict"]


class TopicAvailability(BaseModel):
    topic_id: uuid.UUID
    number: str | None = Field(description="The printed heading number, e.g. 13.1.2")
    title: str
    questions: int = Field(description="Approved, published question families for this topic")


class ChapterAvailability(BaseModel):
    chapter_id: uuid.UUID
    number: int
    title: str
    questions: int = Field(description="Approved, published question families available for practice")
    topics: list[TopicAvailability] = Field(
        default_factory=list, description="Topics with questions, to narrow a chapter test (P11.S3.T1)"
    )


class AvailabilityOut(BaseModel):
    grade: int
    subject: str
    chapters: list[ChapterAvailability]
    seconds_per_question: int | None = Field(
        default=None,
        description="Measured median time per question on submitted untimed practice in this class and subject; "
        "null until enough tests exist (never a guess)",
    )
    estimate_based_on: int = Field(default=0, description="How many submitted tests the estimate was measured from")


class SubjectShare(BaseModel):
    subject: str = Field(min_length=2, max_length=40)
    questions: int = Field(ge=1, le=100)


class FormCreateIn(BaseModel):
    grade: Literal[11, 12]
    subject: str = Field(min_length=2, max_length=40)
    scope: Literal["chapters", "half_book", "full_book", "combined", "multi_subject"] = Field(
        default="chapters",
        description="chapters: the chosen chapters; half_book: first or second half of the book by chapter order; "
        "full_book: every chapter of this class's book; combined: the same subject's Class 11 and 12 books; "
        "multi_subject: custom practice from two to five subjects' whole books in this class, counts from `mix`",
    )
    mix: list[SubjectShare] = Field(
        default_factory=list, max_length=5, description="multi_subject only: questions per subject, in test order"
    )
    half: Literal[1, 2] | None = Field(default=None, description="half_book only")
    chapter_ids: list[uuid.UUID] = Field(default_factory=list, max_length=40)
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


class PassageSnapshot(BaseModel):
    """A shared passage, pinned when the test was built (PASSAGES-01)."""

    id: uuid.UUID
    blocks: list[dict[str, Any]]


class ItemSnapshot(BaseModel):
    """What a learner sees during an attempt. Keys and explanations are never part of this payload."""

    position: int
    marks: int
    stem: list[dict[str, Any]]
    options: list[OptionSnapshot]
    passage: PassageSnapshot | None = None


class AnswerOut(BaseModel):
    position: int
    option_id: str | None
    revision: int
    op_id: uuid.UUID
    saved_at: datetime
    revealed: bool


class NotCountedOut(BaseModel):
    """RECEIPT-01: a question whose latest change wasn't counted, and why."""

    position: int
    reason: Literal["late", "finalised", "invalid"]
    admitted_at: datetime


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
    held_elsewhere: bool = Field(
        default=False, description="Open on another signed-in device; choose continue-here before answering here"
    )
    not_counted: list[NotCountedOut] = Field(
        default_factory=list,
        description="After submission: questions whose latest change wasn't counted (the receipt itself never changes)",
    )
    flagged: list[int] = Field(default_factory=list, description="Positions flagged to come back to (never scored)")


class FlagsIn(BaseModel):
    positions: list[Annotated[int, Field(ge=1, le=200)]] = Field(max_length=200)


class FlagsOut(BaseModel):
    flagged: list[int]


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


class RelatedLesson(BaseModel):
    id: uuid.UUID
    title: str
    chapter_id: uuid.UUID


class ItemReview(BaseModel):
    position: int
    marks: int
    stem: list[dict[str, Any]]
    options: list[OptionSnapshot]
    passage: PassageSnapshot | None = None
    chosen: str | None
    correct_option_id: str
    correct: bool | None
    earned: int
    treatment: str
    explanation: dict[str, Any]
    related_lessons: list[RelatedLesson] = Field(
        default_factory=list, description="Published lessons for this question's topic (or its chapter): revise here"
    )


class ResultTiming(BaseModel):
    started_at: datetime
    finalised_at: datetime | None
    seconds_used: int | None
    time_limit_s: int | None


class ResultForm(BaseModel):
    kind: str
    mode: str
    profile: str | None = Field(description="Exam pattern code, for mocks")
    profile_version: int | None


class ResultSection(BaseModel):
    label: str
    from_position: int
    to_position: int
    raw: int
    maximum: int


class ScoreHistoryEntry(BaseModel):
    version: int
    status: str
    raw: int
    maximum: int
    percentage: Decimal | None
    reason: str
    created_at: datetime


class ResultCounts(BaseModel):
    excluded: int = Field(description="Questions withdrawn after review: not counted at all")
    credited: int = Field(description="Questions credited to everyone after review")
    unanswered: int
    not_scorable: bool


class ComparisonOut(BaseModel):
    """P12.S2.T3 (COMPARISON-01): how a scheduled session's fixed-form result compares with other learners'."""

    state: Literal["published", "too_few", "pending", "not_included"] = Field(
        description="published: a percentile is shown; otherwise `message` says why not"
    )
    message: str
    percentile: Decimal | None = Field(
        default=None, description="100 * (lower + 0.5 * equal) / N, the learner included; one decimal"
    )
    learners: int | None = Field(default=None, description="N: distinct learner accounts compared")
    timing_group: Literal["standard", "accommodated"]
    group: str = Field(description="Who this learner is compared with")
    window_start: datetime | None = None
    window_end: datetime | None = None
    version: int | None = Field(default=None, description="Comparison snapshot version")
    tie_rule: str
    limits: str = Field(description="What the comparison does not show")


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
    timing: ResultTiming | None = None
    form: ResultForm | None = None
    sections: list[ResultSection] = Field(default_factory=list, description="Mocks: one row per pattern section")
    history: list[ScoreHistoryEntry] = Field(default_factory=list, description="Every score version, oldest first")
    counts: ResultCounts | None = None
    not_counted: list[NotCountedOut] = Field(default_factory=list, description="Latest changes that weren't counted")
    comparison: ComparisonOut | None = Field(default=None, description="Scheduled sessions' fixed forms only")


class RevealOut(BaseModel):
    position: int
    chosen: str | None
    correct_option_id: str
    correct: bool
    explanation: dict[str, Any]
