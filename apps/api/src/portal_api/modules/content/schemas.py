from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ItemStateName = Literal["draft", "submitted", "changes_requested", "approved", "published"]
AvailabilityName = Literal["unpublished", "live", "quarantined", "retired"]


KindName = Literal["lesson", "mcq", "written", "rubric"]


class ItemCreateIn(BaseModel):
    kind: KindName = "lesson"
    chapter_id: uuid.UUID | None = Field(
        default=None, description="Required except for rubrics (taken from the question)"
    )
    topic_id: uuid.UUID | None = None
    title: str = Field(min_length=3, max_length=200)
    family_of: uuid.UUID | None = Field(default=None, description="Create a reviewed variant in this question's family")
    parent_item_id: uuid.UUID | None = Field(default=None, description="For a rubric: the written question it marks")


class DraftIn(BaseModel):
    revision: int = Field(ge=1, description="The revision this edit started from; a stale value returns 409.")
    title: str | None = Field(default=None, min_length=3, max_length=200)
    body: dict[str, Any]
    source_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=40)


class ChangeReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class SubmitIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class AssignIn(BaseModel):
    reviewer_id: uuid.UUID | None


class ReviewIn(BaseModel):
    decision: Literal["approve", "request_changes"]
    comment: str = Field(min_length=3, max_length=4000)
    checklist: dict[str, bool] = Field(
        default_factory=dict, description="Checks confirmed by the reviewer; questions require every check to approve"
    )


class QuarantineIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)
    level: Literal["SOFT", "VOID", "KEY_ERROR"] | None = Field(
        default=None, description="Required for questions (§5.7); not used for lessons"
    )


class ValidateIn(BaseModel):
    kind: KindName = "lesson"
    chapter_id: uuid.UUID
    body: dict[str, Any]
    source_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=40)
    for_publication: bool = False


class ValidationOut(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]
    block_types: list[str]


class RightsIn(BaseModel):
    rights: Literal["UNVERIFIED", "CONFIRMED", "DENIED"]
    evidence: str = Field(min_length=10, max_length=2000, description="Where the owner's decision is documented.")


class SourceOut(BaseModel):
    id: uuid.UUID
    source_id: str
    title: str | None
    grade_number: int
    subject_code: str
    pdf_pages: int
    missing_pages: list[Any]
    publication_rights: Literal["UNVERIFIED", "CONFIRMED", "DENIED"]
    publication_rights_evidence: str | None
    publication_rights_set_at: datetime | None


class ReviewOut(BaseModel):
    reviewer: str | None
    decision: Literal["approve", "request_changes"]
    comment: str
    checklist: dict[str, bool]
    created_at: datetime


class VersionOut(BaseModel):
    id: uuid.UUID
    number: int
    status: Literal["draft", "submitted", "changes_requested", "approved", "published", "superseded"]
    revision: int
    content_schema_version: int
    body: dict[str, Any]
    block_types: list[str]
    source_refs: list[dict[str, Any]]
    change_reason: str | None
    created_by: str | None
    contributors: list[str]
    updated_by: str | None
    updated_at: datetime
    submitted_at: datetime | None
    approved_by: str | None
    approved_at: datetime | None
    published_by: str | None
    published_at: datetime | None
    reviews: list[ReviewOut]


class ItemSummary(BaseModel):
    id: uuid.UUID
    kind: KindName
    title: str
    state: ItemStateName
    availability: AvailabilityName
    grade_number: int
    subject_code: str
    chapter_id: uuid.UUID
    chapter_title: str
    topic_id: uuid.UUID | None
    topic_title: str | None
    working_version: int | None
    published_version: int | None
    created_by: str | None
    assigned_reviewer: str | None
    assigned_reviewer_id: uuid.UUID | None
    updated_at: datetime
    open_feedback: int = Field(description="Change requests on the working version not yet addressed.")
    family_id: uuid.UUID | None
    parent_item_id: uuid.UUID | None
    quarantine_level: Literal["SOFT", "VOID", "KEY_ERROR"] | None


class Actions(BaseModel):
    """What the caller may do now. Advisory for the UI; the server re-checks every action."""

    edit: bool
    submit: bool
    withdraw: bool
    review: bool
    claim: bool
    publish: bool
    revise: bool
    quarantine: bool
    release: bool
    retire: bool


class ItemDetail(ItemSummary):
    availability_reason: str | None
    working: VersionOut | None
    published: VersionOut | None
    source: SourceOut
    chapter_pdf_start: int | None
    chapter_pdf_end: int | None
    actions: Actions
    blockers: list[str] = Field(description="Why the next step can't happen yet (e.g. rights unverified).")
    review_checklist: list[str] = Field(description="Checks a reviewer must confirm to approve this kind")
    quarantine_levels: list[str] = Field(description="Levels a publisher chooses from when quarantining this kind")


class HistoryEvent(BaseModel):
    at: datetime
    action: str
    actor: str | None
    details: dict[str, Any]


class LessonOut(BaseModel):
    id: uuid.UUID
    title: str
    topic_id: uuid.UUID | None
    version: int
    published_at: datetime
    content_schema_version: int
    block_types: list[str]
    body: dict[str, Any]
    source_refs: list[dict[str, Any]]
