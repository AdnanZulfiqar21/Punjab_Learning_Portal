"""Content search (roadmap P11.S2.T3; SEARCH-01).

One search box over the published catalogue (chapters and topics, as before) and, when the client asks for them with
`lessons=true`, published lessons. Older app builds don't send it and keep getting exactly the chapter and topic hits
they know how to show.

* **What a lesson match may use.** Every learner can find a live lesson by its title (titles are listed on the chapter
  page for everyone, marked locked when premium). Lesson *text* is matched, and quoted in a snippet, only where the
  caller may read it: free previews for everyone, premium lessons for a plan or trial that covers that class and
  subject (the same rule as the chapter page, review R07). So a search never tells a learner what a lesson they can't
  read says. Opening a result goes through the chapter page, which checks publication and access again.
* **What text is searchable.** `lesson_search_text(body)`, a database function (migration `f6a1c3e8b204`), is the one
  definition: it leaves out checkpoints and worked-example answers, so a snippet never gives an answer away. Only a
  live item's *published* version is searched; drafts, quarantined and retired items, and questions (whose keys stay
  isolated, P08.S2.T3) never are.
* **How it matches.** PostgreSQL full-text search (English stemming; Urdu and Roman Urdu words match as written) for
  lesson text, trigram similarity for typos in titles, and the curated **alias table**: a reviewed group of equivalent
  terms in English, Urdu script and Roman Urdu spellings, scoped to one class and subject, with the owner material it
  comes from. A query containing one form is also searched with the others. Only approved groups are used; a group
  is proposed by one person and approved by another in scope. The table starts empty: its terms come from the
  owner's material (BLOCKERS B16), never from us.
* **Lecture transcripts** are not searched: no lecture is released to learners yet (B05). They join here when one is.

Search terms are never logged, audited or counted (ISOLATION-01).
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    and_,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_session
from portal_api.errors import Conflict, Forbidden, NotFound, Unprocessable
from portal_api.modules.access import service as access
from portal_api.modules.audit.models import record
from portal_api.modules.content import kinds, workflow
from portal_api.modules.content.router import studio_member
from portal_api.modules.curriculum.models import BookEdition, Grade, Subject
from portal_api.modules.curriculum.schemas import SearchHit, SearchOut, SnippetPart
from portal_api.modules.curriculum.service import normalise_subject
from portal_api.modules.identity.deps import OptionalPrincipal, Principal
from portal_api.modules.identity.permissions import Permission, permissions_for

public = APIRouter(prefix="/v1", tags=["search"])
studio = APIRouter(prefix="/v1/studio", tags=["studio"])
DB = Annotated[Session, Depends(get_session)]
Member = Annotated[Principal, Depends(studio_member)]

LANGUAGES = ("en", "ur", "roman_ur")
# Typo tolerance without unrelated suffix matches (measured on real titles, e.g. "photosyntesis"→0.71,
# "Synthesis of …"→0.47 for "photosynthesis"). The relevance benchmark is P11.S2.T4.
FUZZY_THRESHOLD = 0.65
ALIAS_SIMILARITY = 0.7  # a whole query this close to an approved form counts as that form (Roman Urdu spellings vary)
MAX_ALIAS_GROUPS = 5
MAX_TERMS = 10
LESSON_KINDS = [k.name for k in kinds.KINDS.values() if k.learner_readable]

# Keep in step with the migration (f6a1c3e8b204): Arabic yeh and kaf fold to their Urdu forms; diacritics, tatweel
# and joiners go. The snippet markers (\x02, \x03) can never come from the text itself.
FOLD = {0x064A: "ی", 0x0649: "ی", 0x0643: "ک"}
DROP = [*range(0x064B, 0x0660), 0x0670, 0x0640, 0x200C, 0x200D, 0x02, 0x03]
_TABLE = {**FOLD, **dict.fromkeys(DROP)}
_ARABIC_SCRIPT = re.compile(r"[؀-ۿ]")
START, STOP = "\x02", "\x03"
HEADLINE = (
    f'StartSel={START}, StopSel={STOP}, MaxWords=28, MinWords=10, ShortWord=2, MaxFragments=2, FragmentDelimiter=" … "'
)


def normalise(term: str) -> str:
    """The comparable form of a query or alias: NFKC, Urdu letter folding, case-folded, punctuation as spaces."""
    t = unicodedata.normalize("NFKC", term).translate(_TABLE).casefold()
    return " ".join(re.sub(r"[^\w\s'-]", " ", t).replace("_", " ").split())


# ------------------------------------------------------------------ alias table
class SearchAliasGroup(Base):
    """Equivalent search terms for one class and subject, from the owner's material (`source_ref`)."""

    __tablename__ = "search_alias_group"
    __table_args__ = (
        CheckConstraint("grade_number in (11, 12)", name="search_alias_group_grade"),
        CheckConstraint("status in ('proposed','approved','retired')", name="search_alias_group_status"),
        CheckConstraint("approved_by is null or approved_by <> proposed_by", name="search_alias_group_independent"),
        CheckConstraint(
            "status <> 'approved' or approved_by is not null", name="search_alias_group_approved_has_approver"
        ),
        Index("ix_search_alias_group_scope", "grade_number", "subject_code", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(10), default="proposed")
    source_ref: Mapped[str] = mapped_column(String(300))
    proposed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_reason: Mapped[str | None] = mapped_column(String(300))


class SearchAlias(Base):
    __tablename__ = "search_alias"
    __table_args__ = (
        CheckConstraint("language in ('en','ur','roman_ur')", name="search_alias_language"),
        UniqueConstraint("group_id", "normalized", name="uq_search_alias_form"),
        Index("ix_search_alias_normalized", "normalized"),
        Index(
            "ix_search_alias_normalized_trgm",
            "normalized",
            postgresql_using="gin",
            postgresql_ops={"normalized": "gin_trgm_ops"},
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_alias_group.id", ondelete="RESTRICT"))
    language: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(String(80))
    normalized: Mapped[str] = mapped_column(String(80))


def expand(db: Session, query: str, grade: int | None, subject: str | None) -> list[str]:
    """Other forms of the query from approved alias groups: each form found in the query (as whole words) is swapped
    for its equivalents; a whole query that is a near spelling of a form brings in that group's forms."""
    words = query.split()
    grams = {" ".join(words[i:j]) for i in range(len(words)) for j in range(i + 1, min(len(words), i + 4) + 1)}
    near = func.similarity(SearchAlias.normalized, query)
    match = (
        or_(SearchAlias.normalized.in_(grams), near >= ALIAS_SIMILARITY)
        if len(query) >= 4
        else (SearchAlias.normalized.in_(grams))
    )
    scope = [SearchAliasGroup.status == "approved", match]
    if grade is not None:
        scope.append(SearchAliasGroup.grade_number == grade)
    if subject is not None:
        scope.append(SearchAliasGroup.subject_code == subject)
    rows = db.execute(
        select(SearchAlias.group_id, SearchAlias.normalized, SearchAlias.normalized.in_(grams).label("exact"))
        .join(SearchAliasGroup, SearchAliasGroup.id == SearchAlias.group_id)
        .where(and_(*scope))
        .order_by(SearchAlias.normalized.in_(grams).desc(), near.desc())
    ).all()
    matched: dict[uuid.UUID, list[tuple[str, bool]]] = {}
    for group_id, form, exact in rows:
        if group_id in matched or len(matched) < MAX_ALIAS_GROUPS:
            matched.setdefault(group_id, []).append((form, bool(exact)))
    if not matched:
        return []
    forms: dict[uuid.UUID, list[str]] = {}
    for group_id, form in db.execute(
        select(SearchAlias.group_id, SearchAlias.normalized)
        .where(SearchAlias.group_id.in_(matched))
        .order_by(SearchAlias.language, SearchAlias.normalized)
    ):
        forms.setdefault(group_id, []).append(form)
    out: list[str] = []
    for group_id, hits in matched.items():
        for form, exact in hits:
            if exact:
                pattern = re.compile(rf"(?<!\S){re.escape(form)}(?!\S)")
                out += [pattern.sub(other, query, count=1) for other in forms[group_id] if other != form]
            else:
                out += forms[group_id]
    return list(dict.fromkeys(t for t in out if t != query))[: MAX_TERMS - 1]


# ------------------------------------------------------------------ search
STRUCTURE_SQL = text("""
WITH terms AS (SELECT DISTINCT unnest(CAST(:terms AS text[])) AS q)
SELECT * FROM (
  SELECT DISTINCT ON (kind, id) * FROM (
    SELECT 'topic' AS kind, t.id, c.id AS chapter_id, t.title, t.number, c.title AS chapter_title, g.number AS grade,
           s.code AS subject_code, s.name AS subject_name, t.pdf_page,
           CASE WHEN t.title ILIKE '%' || q.q || '%' THEN 1.0 ELSE strict_word_similarity(q.q, t.title) END AS score
      FROM topic t JOIN chapter c ON c.id = t.chapter_id JOIN book_edition b ON b.id = c.book_id
      JOIN grade g ON g.id = b.grade_id JOIN subject s ON s.id = b.subject_id, terms q
     WHERE s.active AND t.retired_at IS NULL AND c.retired_at IS NULL
           AND (t.title ILIKE '%' || q.q || '%' OR strict_word_similarity(q.q, t.title) >= :fuzzy)
           AND (CAST(:grade AS int) IS NULL OR g.number = CAST(:grade AS int))
           AND (CAST(:subject AS text) IS NULL OR s.code = CAST(:subject AS text))
    UNION ALL
    SELECT 'chapter', c.id, c.id, c.title, CAST(c.number AS text), c.title, g.number, s.code, s.name, c.pdf_start,
           CASE WHEN c.title ILIKE '%' || q.q || '%' THEN 1.05 ELSE strict_word_similarity(q.q, c.title) + 0.05 END
      FROM chapter c JOIN book_edition b ON b.id = c.book_id JOIN grade g ON g.id = b.grade_id
      JOIN subject s ON s.id = b.subject_id, terms q
     WHERE s.active AND c.retired_at IS NULL
           AND (c.title ILIKE '%' || q.q || '%' OR strict_word_similarity(q.q, c.title) >= :fuzzy)
           AND (CAST(:grade AS int) IS NULL OR g.number = CAST(:grade AS int))
           AND (CAST(:subject AS text) IS NULL OR s.code = CAST(:subject AS text))
  ) hits ORDER BY kind, id, score DESC
) best ORDER BY score DESC, grade, title LIMIT :limit
""")

# A live lesson's published version only. Title matches for everyone; text matches (and snippets) only where the
# caller may read the lesson. The text match uses the GIN index on to_tsvector('english', lesson_search_text(body)).
LESSON_SQL = text("""
WITH terms AS (SELECT DISTINCT unnest(CAST(:terms AS text[])) AS q),
tq AS (
  SELECT CAST(string_agg('(' || CAST(plainto_tsquery('english', q) AS text) || ')', ' | ') AS tsquery) AS tq
    FROM terms WHERE numnode(plainto_tsquery('english', q)) > 0
),
text_hits AS (
  SELECT v.id, ts_rank_cd(to_tsvector('english'::regconfig, lesson_search_text(v.body)), tq.tq, 32) AS rank
    FROM content_version v, tq
   WHERE tq.tq IS NOT NULL AND to_tsvector('english'::regconfig, lesson_search_text(v.body)) @@ tq.tq
),
cand AS (
  SELECT i.id, i.title, i.language, i.access_tier, c.id AS chapter_id, c.title AS chapter_title, g.number AS grade,
         s.code AS subject_code, s.name AS subject_name, v.body,
         (i.access_tier = 'preview' OR CAST(g.number AS text) || ':' || s.code = ANY(CAST(:readable AS text[])))
           AS readable,
         (SELECT max(CASE WHEN i.title ILIKE '%' || t.q || '%' THEN 1.1
                          WHEN strict_word_similarity(t.q, i.title) >= :fuzzy
                          THEN strict_word_similarity(t.q, i.title) + 0.1 END) FROM terms t) AS title_score,
         h.rank
    FROM content_item i
    JOIN content_version v ON v.id = i.published_version_id
    JOIN chapter c ON c.id = i.chapter_id JOIN book_edition b ON b.id = c.book_id
    JOIN grade g ON g.id = b.grade_id JOIN subject s ON s.id = b.subject_id
    LEFT JOIN text_hits h ON h.id = v.id
   WHERE i.availability = 'live' AND i.kind = ANY(CAST(:kinds AS text[])) AND s.active AND c.retired_at IS NULL
         AND (CAST(:grade AS int) IS NULL OR g.number = CAST(:grade AS int))
         AND (CAST(:subject AS text) IS NULL OR s.code = CAST(:subject AS text))
),
scored AS (
  SELECT cand.*, CASE WHEN readable AND rank IS NOT NULL THEN 0.6 + 0.35 * rank END AS text_score FROM cand
)
SELECT id, title, language, access_tier, chapter_id, chapter_title, grade, subject_code, subject_name, readable,
       greatest(title_score, text_score) AS score,
       CASE WHEN text_score IS NOT NULL
            THEN ts_headline('english', lesson_search_text(body), (SELECT tq FROM tq), :headline) END AS snippet
  FROM scored
 WHERE title_score IS NOT NULL OR text_score IS NOT NULL
 ORDER BY score DESC, grade, title
 LIMIT :limit
""")


def _readable(db: Session, who: Principal | None) -> list[str]:
    """`grade:subject` pairs whose premium lessons this caller may read (none for a guest or a gated trial device)."""
    if who is None:
        return []
    ents = access.active_entitlements(db, who.user.id, access.db_now(db))
    if not ents or access.device_gate(db, who.user.id) is not None:
        return []
    pairs = db.execute(
        select(Grade.number, Subject.code)
        .join(BookEdition, BookEdition.grade_id == Grade.id)
        .join(Subject, Subject.id == BookEdition.subject_id)
        .where(Subject.active)
        .distinct()
    ).all()
    return [f"{g}:{s}" for g, s in pairs if any(access.covers(e, access.Need.subjects(g, s)) for e in ents)]


def _snippet(raw: str | None) -> list[SnippetPart]:
    if not raw:
        return []
    parts = []
    for chunk in re.split(f"({START}[^{STOP}]*{STOP})", raw):
        if chunk.startswith(START):
            parts.append(SnippetPart(text=chunk[1:-1], match=True))
        elif chunk:
            parts.append(SnippetPart(text=chunk, match=False))
    return parts


def run_search(
    db: Session,
    who: Principal | None,
    *,
    q: str,
    grade: int | None,
    subject: str | None,
    limit: int,
    lessons: bool,
) -> SearchOut:
    subj = normalise_subject(subject) if subject else None
    raw, folded = q.strip(), normalise(q)
    also = expand(db, folded, grade, subj) if folded else []
    terms = list(dict.fromkeys([raw, *([folded] if folded else []), *also]))
    params = {"terms": terms, "grade": grade, "subject": subj, "limit": limit, "fuzzy": FUZZY_THRESHOLD}
    hits = [SearchHit(**{**r, "score": float(r["score"])}) for r in db.execute(STRUCTURE_SQL, params).mappings()]
    if lessons:
        rows = db.execute(
            LESSON_SQL, {**params, "kinds": LESSON_KINDS, "readable": _readable(db, who), "headline": HEADLINE}
        ).mappings()
        hits += [
            SearchHit(
                kind="lesson",
                id=r["id"],
                chapter_id=r["chapter_id"],
                title=r["title"],
                number=None,
                chapter_title=r["chapter_title"],
                grade=r["grade"],
                subject_code=r["subject_code"],
                subject_name=r["subject_name"],
                pdf_page=None,
                score=float(r["score"]),
                language=r["language"],
                access_tier=r["access_tier"],
                locked=not r["readable"],
                snippet=_snippet(r["snippet"]),
            )
            for r in rows
        ]
        hits.sort(key=lambda h: (-h.score, h.grade, h.title))
    return SearchOut(query=q, grade=grade, subject=subj, hits=hits[:limit], also_searched=also, lessons=lessons)


@public.get(
    "/search",
    response_model=SearchOut,
    summary="Search chapters and topics, and with lessons=true the published lessons the caller can see; every hit is "
    "labelled with its grade",
)
def search(
    db: DB,
    who: OptionalPrincipal,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    grade: Annotated[int | None, Query(ge=11, le=12)] = None,
    subject: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    lessons: bool = False,
) -> SearchOut:
    return run_search(db, who, q=q, grade=grade, subject=subject, limit=limit, lessons=lessons)


# ------------------------------------------------------------------ studio: curating the alias table
class SearchTermForm(BaseModel):
    language: Literal["en", "ur", "roman_ur"]
    text: str = Field(min_length=1, max_length=80)


class SearchTermGroupIn(BaseModel):
    grade: int = Field(ge=11, le=12)
    subject: str = Field(min_length=2, max_length=40)
    forms: list[SearchTermForm] = Field(min_length=2, max_length=12)
    source_ref: str = Field(min_length=3, max_length=300, description="Where in the owner's material these come from")


class SearchTermRetireIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class SearchTermGroupOut(BaseModel):
    id: uuid.UUID
    grade: int
    subject: str
    status: Literal["proposed", "approved", "retired"]
    forms: list[SearchTermForm]
    source_ref: str
    proposed_at: datetime
    approved_at: datetime | None
    retired_reason: str | None
    mine: bool
    can_approve: bool
    can_retire: bool


def _perms(db: Session, who: Principal, grade: int, subject: str) -> set[Permission]:
    return set(permissions_for(workflow.roles_in_scope(db, who.user.id, grade, subject)))


def _out(db: Session, who: Principal, g: SearchAliasGroup) -> SearchTermGroupOut:
    perms = _perms(db, who, g.grade_number, g.subject_code)
    forms = db.scalars(
        select(SearchAlias).where(SearchAlias.group_id == g.id).order_by(SearchAlias.language, SearchAlias.text)
    )
    return SearchTermGroupOut(
        id=g.id,
        grade=g.grade_number,
        subject=g.subject_code,
        status=g.status,  # type: ignore[arg-type]
        forms=[SearchTermForm(language=f.language, text=f.text) for f in forms],  # type: ignore[arg-type]
        source_ref=g.source_ref,
        proposed_at=g.proposed_at,
        approved_at=g.approved_at,
        retired_reason=g.retired_reason,
        mine=g.proposed_by == who.user.id,
        can_approve=g.status == "proposed" and g.proposed_by != who.user.id and Permission.review_content in perms,
        can_retire=g.status != "retired" and Permission.review_content in perms,
    )


def _lock_scope(db: Session, grade: int, subject: str) -> None:
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"search_alias:{grade}:{subject}"})


def _clashes(db: Session, grade: int, subject: str, forms: list[str], statuses: tuple[str, ...]) -> list[str]:
    return list(
        db.scalars(
            select(SearchAlias.text)
            .join(SearchAliasGroup, SearchAliasGroup.id == SearchAlias.group_id)
            .where(
                SearchAliasGroup.grade_number == grade,
                SearchAliasGroup.subject_code == subject,
                SearchAliasGroup.status.in_(statuses),
                SearchAlias.normalized.in_(forms),
            )
        )
    )


def _scoped_group(db: Session, who: Principal, group_id: uuid.UUID, permission: Permission) -> SearchAliasGroup:
    g = db.get(SearchAliasGroup, group_id, with_for_update=True)
    if g is None or not _perms(db, who, g.grade_number, g.subject_code) & {
        Permission.draft_content,
        Permission.review_content,
        Permission.publish_content,
    }:
        raise NotFound("Search term group not found.")  # don't reveal groups outside the caller's scope
    if permission not in _perms(db, who, g.grade_number, g.subject_code):
        raise Forbidden("Your role in this class and subject can't do this.")
    return g


@studio.get(
    "/search-terms",
    response_model=list[SearchTermGroupOut],
    summary="Search term groups (English, Urdu, Roman Urdu) for one class and subject (content staff in scope)",
)
def list_terms(
    db: DB,
    who: Member,
    grade: Annotated[int, Query(ge=11, le=12)],
    subject: Annotated[str, Query(min_length=2, max_length=40)],
) -> list[SearchTermGroupOut]:
    subj = normalise_subject(subject)
    if not _perms(db, who, grade, subj) & {
        Permission.draft_content,
        Permission.review_content,
        Permission.publish_content,
    }:
        raise Forbidden("This class and subject are outside your role's scope.")
    groups = db.scalars(
        select(SearchAliasGroup)
        .where(SearchAliasGroup.grade_number == grade, SearchAliasGroup.subject_code == subj)
        .order_by(SearchAliasGroup.status, SearchAliasGroup.proposed_at.desc())
    )
    return [_out(db, who, g) for g in groups]


@studio.post(
    "/search-terms",
    response_model=SearchTermGroupOut,
    status_code=201,
    summary="Propose a group of equivalent search terms from the owner's material (authors in scope; audited)",
)
def propose_terms(db: DB, who: Member, body: SearchTermGroupIn) -> SearchTermGroupOut:
    subj = normalise_subject(body.subject)
    if db.scalar(select(Subject.id).where(Subject.code == subj, Subject.active)) is None:
        raise NotFound("Subject not found.")
    if Permission.draft_content not in _perms(db, who, body.grade, subj):
        raise Forbidden("Proposing search terms needs an author role for this class and subject.")
    forms: list[tuple[str, str, str]] = []
    for f in body.forms:
        shown, norm = " ".join(f.text.split()), normalise(f.text)
        if not norm:
            raise Unprocessable(f"“{f.text}” has no letters to search for.")
        urdu = bool(_ARABIC_SCRIPT.search(shown))
        if urdu != (f.language == "ur"):
            raise Unprocessable(
                f"“{shown}” is marked {f.language}, but "
                + ("Urdu forms use Urdu script." if f.language == "ur" else "only Urdu forms use Urdu script.")
            )
        if norm in {n for _, _, n in forms}:
            raise Unprocessable(f"“{shown}” appears twice in this group.")
        forms.append((f.language, shown, norm))
    _lock_scope(db, body.grade, subj)
    clash = _clashes(db, body.grade, subj, [n for _, _, n in forms], ("proposed", "approved"))
    if clash:
        raise Conflict(f"Already in another group for this class and subject: {', '.join(sorted(clash))}.")
    g = SearchAliasGroup(
        grade_number=body.grade,
        subject_code=subj,
        status="proposed",
        source_ref=" ".join(body.source_ref.split()),
        proposed_by=who.user.id,
    )
    db.add(g)
    db.flush()
    db.add_all(SearchAlias(group_id=g.id, language=lang, text=shown, normalized=n) for lang, shown, n in forms)
    record(
        db,
        actor=who.user.id,
        action="search_terms.proposed",
        target_type="search_alias_group",
        target_id=str(g.id),
        details={"grade": body.grade, "subject": subj, "forms": [s for _, s, _ in forms], "source": g.source_ref},
    )
    db.commit()
    db.refresh(g)
    return _out(db, who, g)


@studio.post(
    "/search-terms/{group_id}/approve",
    response_model=SearchTermGroupOut,
    summary="Approve a proposed group so search uses it (a subject reviewer in scope who didn't propose it; audited)",
)
def approve_terms(db: DB, who: Member, group_id: uuid.UUID) -> SearchTermGroupOut:
    g = _scoped_group(db, who, group_id, Permission.review_content)
    if g.status != "proposed":
        raise Conflict(f"This group is {g.status}; only a proposed group can be approved.")
    if g.proposed_by == who.user.id:
        raise Forbidden("You proposed this group, so someone else must approve it.")
    _lock_scope(db, g.grade_number, g.subject_code)
    forms = list(db.scalars(select(SearchAlias.normalized).where(SearchAlias.group_id == g.id)))
    clash = _clashes(db, g.grade_number, g.subject_code, forms, ("approved",))
    if clash:
        raise Conflict(f"Already approved in another group: {', '.join(sorted(clash))}. Retire one of them first.")
    g.status, g.approved_by, g.approved_at = "approved", who.user.id, access.db_now(db)
    record(db, actor=who.user.id, action="search_terms.approved", target_type="search_alias_group", target_id=str(g.id))
    db.commit()
    db.refresh(g)
    return _out(db, who, g)


@studio.post(
    "/search-terms/{group_id}/retire",
    response_model=SearchTermGroupOut,
    summary="Stop using a group in search, with a reason (subject reviewers in scope; audited; never deleted)",
)
def retire_terms(db: DB, who: Member, group_id: uuid.UUID, body: SearchTermRetireIn) -> SearchTermGroupOut:
    g = _scoped_group(db, who, group_id, Permission.review_content)
    if g.status == "retired":
        raise Conflict("This group is already retired.")
    g.status, g.retired_by, g.retired_at = "retired", who.user.id, access.db_now(db)
    g.retired_reason = " ".join(body.reason.split())
    record(
        db,
        actor=who.user.id,
        action="search_terms.retired",
        target_type="search_alias_group",
        target_id=str(g.id),
        details={"reason": g.retired_reason},
    )
    db.commit()
    db.refresh(g)
    return _out(db, who, g)
