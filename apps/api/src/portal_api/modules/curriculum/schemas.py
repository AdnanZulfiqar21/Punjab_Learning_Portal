from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GradeOut(_Out):
    id: uuid.UUID
    number: int
    code: str
    name: str


class SubjectOut(_Out):
    id: uuid.UUID
    code: str
    name: str
    aliases: list[str]


class BookSummary(_Out):
    id: uuid.UUID
    title: str | None
    source_id: str
    chapter_label: str
    chapter_count: int
    completeness: str


class SubjectInGrade(BaseModel):
    subject: SubjectOut
    books: list[BookSummary]


class GradeCatalogue(BaseModel):
    grade: GradeOut
    subjects: list[SubjectInGrade]


class CatalogueOut(BaseModel):
    region: str
    scope_decision: str
    grades: list[GradeCatalogue]


class SourceRef(BaseModel):
    """Where a chapter/topic lives in the owner's original file (PDF pages are 1-based file indices)."""

    source_id: str
    file: str
    sha256: str
    pdf_start: int | None
    pdf_end: int | None
    printed_start: int | None
    printed_end: int | None
    page_rule: str | None


class ChapterSummary(_Out):
    id: uuid.UUID
    display_order: int
    number: int
    contents_number: int | None
    title: str
    status: str
    pdf_start: int | None
    pdf_end: int | None
    printed_start: int | None
    printed_end: int | None
    topic_count: int
    visual_count: int
    assessment_counts: dict[str, int]
    content_state: str


class Breadcrumb(BaseModel):
    grade: GradeOut
    subject: SubjectOut
    book_id: uuid.UUID
    book_title: str | None
    source_id: str
    chapter_label: str


class BookOut(BaseModel):
    breadcrumb: Breadcrumb
    completeness: str
    missing_pages: list[str]
    edition: str | None
    authority: str | None
    chapters: list[ChapterSummary]


class TopicNode(BaseModel):
    id: uuid.UUID
    number: str | None
    title: str
    depth: int
    pdf_page: int | None
    points: list[str]
    children: list[TopicNode]


class ChapterOut(BaseModel):
    id: uuid.UUID
    breadcrumb: Breadcrumb
    number: int
    contents_number: int | None
    title: str
    status: str
    main_concept: str | None
    slo_codes: str | None
    key_terms: list[str]
    visual_count: int
    assessment_counts: dict[str, int]
    content_state: str
    source: SourceRef
    topics: list[TopicNode]
    previous_chapter_id: uuid.UUID | None
    next_chapter_id: uuid.UUID | None


class SearchHit(BaseModel):
    kind: str  # "chapter" | "topic"
    id: uuid.UUID
    chapter_id: uuid.UUID
    title: str
    number: str | None
    chapter_title: str
    grade: int
    subject_code: str
    subject_name: str
    pdf_page: int | None
    score: float


class SearchOut(BaseModel):
    query: str
    grade: int | None
    subject: str | None
    hits: list[SearchHit]
