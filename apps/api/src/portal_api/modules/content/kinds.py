"""Content kinds that share the editorial workflow (authoring, scoped independent review, rights gate, publication,
quarantine, retirement). Each kind supplies its own body schema, submission/publication validation, the checks a
reviewer must confirm, and whether published versions are learner-readable through the lessons API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from portal_api.modules.content import blocks, mcq, written


@dataclass(frozen=True)
class KindSpec:
    name: str
    label: str
    empty_body: Callable[[], dict[str, Any]]
    # Normalise a draft body: (normalised body, schema errors, block types). Drafts may be incomplete.
    parse_draft: Callable[[object], tuple[dict[str, Any] | None, list[str], list[str]]]
    validate: Callable[[object, bool], blocks.Validation]
    review_checklist: tuple[str, ...]
    # Quarantine levels a publisher must choose from (§5.7); empty means a plain hide/unhide.
    quarantine_levels: tuple[str, ...]
    learner_readable: bool  # lessons: yes. Questions: never through content APIs (keys stay protected).


def _lesson_parse(body: object) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    parsed, errors = blocks.parse(body)
    if parsed is None:
        return None, errors, []
    return parsed.model_dump(mode="json", exclude_none=True), [], sorted({b.type for b in parsed.blocks})


def _written_parse(body: object) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    q, errors = written.parse_written(body)
    if q is None:
        return None, errors, []
    return q.model_dump(mode="json", exclude_none=True), [], written.written_block_types(q)


def _rubric_parse(body: object) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    r, errors = written.parse_rubric(body)
    if r is None:
        return None, errors, []
    return r.model_dump(mode="json", exclude_none=True), [], []


def _mcq_parse(body: object) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    q, errors = mcq.parse(body)
    if q is None:
        return None, errors, []
    return q.model_dump(mode="json", exclude_none=True), [], mcq.block_types(q)


KINDS: dict[str, KindSpec] = {
    "lesson": KindSpec(
        name="lesson",
        label="Lesson",
        empty_body=lambda: {"blocks": []},
        parse_draft=_lesson_parse,
        validate=lambda body, pub: blocks.validate_body(body, for_publication=pub),
        review_checklist=(),
        quarantine_levels=(),
        learner_readable=True,
    ),
    "mcq": KindSpec(
        name="mcq",
        label="Multiple-choice question",
        empty_body=lambda: dict(mcq.EMPTY_BODY),
        parse_draft=_mcq_parse,
        validate=lambda body, pub: mcq.validate(body, for_publication=pub),
        review_checklist=mcq.REVIEW_CHECKLIST,
        quarantine_levels=("SOFT", "VOID", "KEY_ERROR"),
        learner_readable=False,
    ),
    "written": KindSpec(
        name="written",
        label="Written question",
        empty_body=lambda: dict(written.WRITTEN_EMPTY),
        parse_draft=_written_parse,
        validate=lambda body, pub: written.validate_written(body, for_publication=pub),
        review_checklist=written.WRITTEN_CHECKLIST,
        quarantine_levels=("SOFT", "VOID"),
        learner_readable=False,
    ),
    "rubric": KindSpec(
        name="rubric",
        label="Marking rubric",
        empty_body=lambda: dict(written.RUBRIC_EMPTY),
        parse_draft=_rubric_parse,
        validate=lambda body, pub: written.validate_rubric(body, for_publication=pub),
        review_checklist=written.RUBRIC_CHECKLIST,
        quarantine_levels=("SOFT",),
        learner_readable=False,  # rubrics are marking secrets until a result is released
    ),
}


def get(kind: str) -> KindSpec:
    return KINDS[kind]
