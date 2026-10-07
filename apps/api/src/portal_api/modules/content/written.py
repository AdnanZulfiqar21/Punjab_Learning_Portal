"""Written (handwritten-answer) questions and their rubrics (roadmap §20.6, W01/W04 records).

Marks are stored as **integer hundredths** ("units": 100 = 1 mark, 50 = 0.5). A rubric is its own reviewed content item
linked to a written question; it names the exact question version it marks, its authority (an official scheme only
where one actually exists and is referenced, otherwise an explicitly labelled practice rubric), the permitted increment,
and criteria whose maxima reconcile exactly with the question's subpart and total maxima. Alternative-route criteria
are grouped and capped so a learner can't be credited twice for the same work.

A written question can't be published until a rubric for that exact version is published; a rubric can't be published
for a question version that hasn't been academically approved.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from portal_api.modules.content import blocks
from portal_api.modules.content.blocks import Block as ContentBlock

PART_ID = r"^[a-z0-9][a-z0-9_-]{0,11}$"
Units = Annotated[int, Field(ge=0, le=100_000)]


class Subpart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, Field(pattern=PART_ID)]
    label: Annotated[str, Field(min_length=1, max_length=20)]
    blocks: list[ContentBlock] = Field(default_factory=list, max_length=20)
    max_units: Units = 0


class WrittenBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: Literal["short", "long"] = "short"
    stem: list[ContentBlock] = Field(default_factory=list, max_length=40)
    subparts: list[Subpart] = Field(default_factory=list, max_length=12)
    max_units: Units = 0
    answer_language: Literal["en", "ur"] = "en"
    expected_structures: list[Literal["diagram", "equation", "table", "chemical_structure", "code"]] = Field(
        default_factory=list
    )
    origin: Literal["original_practice", "authorised_past_paper"] = "original_practice"
    past_paper_ref: Annotated[str, Field(max_length=300)] | None = None


class Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, Field(pattern=PART_ID)]
    subpart_id: Annotated[str, Field(pattern=PART_ID)] | None = None
    description: Annotated[str, Field(max_length=2000)] = ""
    max_units: Units = 0
    levels: list[Units] = Field(default_factory=list, max_length=20)  # permitted awards, in units
    depends_on: list[Annotated[str, Field(pattern=PART_ID)]] = Field(default_factory=list)
    alternative_group: Annotated[str, Field(pattern=PART_ID)] | None = None
    evidence: Annotated[str, Field(max_length=1000)] | None = None
    misconceptions: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=10)


class RubricBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_version_id: uuid.UUID | None = None
    authority: Literal["official_scheme", "practice_rubric"] = "practice_rubric"
    authority_ref: Annotated[str, Field(max_length=300)] | None = None  # where an official scheme is published
    increment_units: int = Field(default=50, ge=1, le=100)
    criteria: list[Criterion] = Field(default_factory=list, max_length=60)
    expected_concepts: list[Annotated[str, Field(max_length=500)]] = Field(default_factory=list, max_length=40)
    alternative_routes: list[Annotated[str, Field(max_length=1000)]] = Field(default_factory=list, max_length=20)
    consequential_error_rule: Annotated[str, Field(max_length=1000)] | None = None
    units_rule: Annotated[str, Field(max_length=1000)] | None = None
    crossed_out_rule: Annotated[str, Field(max_length=1000)] | None = None


_written = TypeAdapter(WrittenBody)
_rubric = TypeAdapter(RubricBody)

WRITTEN_EMPTY: dict[str, object] = {"question_type": "short", "stem": [], "subparts": [], "max_units": 0}
RUBRIC_EMPTY: dict[str, object] = {"authority": "practice_rubric", "increment_units": 50, "criteria": []}


def _errors(e: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()]


def parse_written(body: object) -> tuple[WrittenBody | None, list[str]]:
    try:
        return _written.validate_python(body), []
    except ValidationError as e:
        return None, _errors(e)


def parse_rubric(body: object) -> tuple[RubricBody | None, list[str]]:
    try:
        return _rubric.validate_python(body), []
    except ValidationError as e:
        return None, _errors(e)


def written_block_types(q: WrittenBody) -> list[str]:
    return sorted({b.type for b in q.stem} | {b.type for s in q.subparts for b in s.blocks})


def subpart_maxima(q: WrittenBody) -> dict[str | None, int]:
    """Scorable slots: one per subpart, or the whole question when it has none."""
    return {s.id: s.max_units for s in q.subparts} if q.subparts else {None: q.max_units}


def validate_written(body: object, *, for_publication: bool) -> blocks.Validation:
    q, errors = parse_written(body)
    if q is None:
        return blocks.Validation(errors, [], [])
    warnings: list[str] = []
    if not q.stem:
        errors.append("Write the question.")
    if q.max_units <= 0:
        errors.append("The question needs a positive maximum mark.")
    ids = [s.id for s in q.subparts]
    if len(set(ids)) != len(ids):
        errors.append("Subpart IDs must be unique.")
    if q.subparts:
        if any(s.max_units <= 0 for s in q.subparts):
            errors.append("Every subpart needs a positive maximum mark.")
        if sum(s.max_units for s in q.subparts) != q.max_units:
            errors.append("Subpart maxima must add up to the question maximum.")
    if q.origin == "authorised_past_paper" and not q.past_paper_ref:
        errors.append("Past-paper questions need a reference to where reuse is authorised.")
    where_blocks = [("stem", q.stem)] + [(f"subparts[{s.id}]", s.blocks) for s in q.subparts]
    for where, bl in where_blocks:
        r_err, r_warn = blocks.check_renderers(bl, for_publication=for_publication, where=where)
        errors += r_err
        warnings += r_warn
    return blocks.Validation(errors, warnings, written_block_types(q))


def validate_rubric(body: object, *, for_publication: bool) -> blocks.Validation:
    """Rubric-internal rules. Reconciliation against the question version is `reconcile` (needs the question)."""
    r, errors = parse_rubric(body)
    if r is None:
        return blocks.Validation(errors, [], [])
    warnings: list[str] = []
    if r.question_version_id is None:
        errors.append("Choose the question version this rubric marks.")
    if r.authority == "official_scheme" and not r.authority_ref:
        errors.append("An official marking scheme needs a reference to where it is published.")
    if not r.criteria:
        errors.append("Add at least one criterion.")
    ids = [c.id for c in r.criteria]
    if len(set(ids)) != len(ids):
        errors.append("Criterion IDs must be unique.")
    known = set(ids)
    for c in r.criteria:
        if c.max_units <= 0:
            errors.append(f"Criterion {c.id} needs a positive maximum.")
        if c.max_units % r.increment_units:
            errors.append(f"Criterion {c.id}: maximum must be a multiple of the increment ({r.increment_units}).")
        levels = sorted(set(c.levels))
        if not levels or levels[0] != 0 or levels[-1] != c.max_units:
            errors.append(f"Criterion {c.id}: permitted awards must include 0 and its maximum.")
        if any(v % r.increment_units for v in levels):
            errors.append(f"Criterion {c.id}: every award must be a multiple of the increment ({r.increment_units}).")
        if not c.description.strip():
            errors.append(f"Criterion {c.id}: describe what earns credit.")
        missing = set(c.depends_on) - known
        if missing or c.id in c.depends_on:
            errors.append(f"Criterion {c.id}: depends on unknown criteria {sorted(missing) or [c.id]}.")
    if not r.expected_concepts:
        warnings.append("List the expected concepts so reviewers can check equivalent wording consistently.")
    return blocks.Validation(errors, warnings, [])


def slot_totals(r: RubricBody) -> dict[str | None, int]:
    """Maximum creditable units per slot. Criteria in one alternative group count once, at the group's largest max."""
    totals: dict[str | None, int] = defaultdict(int)
    groups: dict[tuple[str | None, str], int] = {}
    for c in r.criteria:
        if c.alternative_group:
            key = (c.subpart_id, c.alternative_group)
            groups[key] = max(groups.get(key, 0), c.max_units)
        else:
            totals[c.subpart_id] += c.max_units
    for (slot, _), cap in groups.items():
        totals[slot] += cap
    return dict(totals)


def reconcile(r: RubricBody, q: WrittenBody) -> list[str]:
    """Every permitted award and maximum must reconcile with the question (§20.6.3)."""
    errors: list[str] = []
    slots = subpart_maxima(q)
    for c in r.criteria:
        if c.subpart_id not in slots:
            where = "the whole question" if c.subpart_id is None else f"subpart {c.subpart_id}"
            errors.append(f"Criterion {c.id} refers to {where}, which this question version doesn't have as a slot.")
    totals = slot_totals(r)
    for slot, maximum in slots.items():
        got = totals.get(slot, 0)
        if got != maximum:
            label = "the question" if slot is None else f"subpart {slot}"
            errors.append(f"Criteria for {label} add up to {got} units but its maximum is {maximum}.")
    return errors


WRITTEN_CHECKLIST = ("accuracy", "ambiguity", "mapping", "marks", "structures")
RUBRIC_CHECKLIST = ("authority", "reconciliation", "alternative_routes", "consequential_errors", "units_and_wording")
