"""Reviewer preview of a sample form for an exam-profile version (roadmap P09.S4.T1; FORM-PREVIEW-01).

A reviewer sees what a learner would get *before* a pattern is verified or published: the same generator and section
rules as a real mock (`mocks.select_sections`), drawn reproducibly from a seed, with nothing stored. It shows:

* the learner view (stem and options in the frozen display order, with no key or explanation);
* the oldest supported client's view: every block that client can't render is replaced by its reviewed fallback
  (§5.4 rule 4; after publication there should be none to replace);
* automatic checks for accidental answer hints and unverifiable diagram dependencies.

The answer report (keys and explanations) is a separate request, so the learner view can be shared or screenshotted
without exposing answers. Passages don't exist as a block type yet, so there is nothing to check for them.
"""

from __future__ import annotations

import re
import secrets
import uuid
from typing import Any

from sqlalchemy.orm import Session

from portal_api.errors import NotFound
from portal_api.modules.content import blocks as block_registry

_TEXT_KEYS = ("text", "items", "rows", "caption", "text_alt", "prompt")
_ABOVE = re.compile(r"\b(all|none|both|neither) of the (above|options)\b", re.I)


def _text(node: Any) -> str:
    """Every human-readable string in a block tree (iteratively; block trees are shallow but untrusted)."""
    out: list[str] = []
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, str):
            out.append(n)
        elif isinstance(n, list):
            stack.extend(reversed(n))
        elif isinstance(n, dict):
            stack.extend(n[k] for k in _TEXT_KEYS if k in n)
    return " ".join(out)


def _norm(s: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", s.lower()))


def checks(body: dict[str, Any]) -> list[str]:
    """Accidental answer hints a reviewer should look at (warnings, not verdicts)."""
    out: list[str] = []
    options = {o["id"]: _norm(_text(o.get("blocks", []))) for o in body.get("options", [])}
    key = body.get("correct_option_id")
    stem = _norm(_text(body.get("stem", [])))
    answer = options.get(key, "")
    if answer and len(answer.split()) >= 2 and answer in stem:
        out.append("The correct option's text appears in the question.")
    others = [len(t) for k, t in options.items() if k != key]
    if answer and others and len(answer) >= 1.5 * max(others) and len(answer) - max(others) >= 10:
        out.append("The correct option is much longer than every other option.")
    texts = [t for t in options.values() if t]
    if len(texts) != len(set(texts)):
        out.append("Two options have the same text.")
    if body.get("shuffle_options", True) and any(
        _ABOVE.search(_text(o.get("blocks", []))) for o in body.get("options", [])
    ):
        out.append("Options are shuffled but one says 'all/none of the above', which depends on position.")
    for b in _blocks(body):
        fallback = b.get("fallback") or {}
        if fallback.get("image_asset_id"):
            out.append(
                f"A fallback uses diagram asset {fallback['image_asset_id']}, which can't be checked until the asset "
                "store exists (P07)."
            )
    return out


def _blocks(body: dict[str, Any]) -> list[dict[str, Any]]:
    out = [b for b in body.get("stem", []) if isinstance(b, dict)]
    for o in body.get("options", []):
        out += [b for b in o.get("blocks", []) if isinstance(b, dict)]
    return out


def _oldest(block_list: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """The oldest supported client's rendering: blocks it can't show natively become their reviewed fallback."""
    out, replaced = [], 0
    for b in block_list:
        spec = block_registry.REGISTRY.get(str(b.get("type")))
        needs = spec is not None and any(
            spec.min_renderer[p] > block_registry.SUPPORTED_RENDERER[p] for p in block_registry.PLATFORMS
        )
        if needs:
            replaced += 1
            fb = b.get("fallback") or {}
            out.append({"type": "fallback", "text": fb.get("text", ""), "image_asset_id": fb.get("image_asset_id")})
        else:
            out.append(b)
    return out, replaced


def _sample(db: Session, version_id: uuid.UUID, seed: int) -> tuple[Any, list[dict[str, Any]], list[Any]]:
    from portal_api.modules.assessment import mocks
    from portal_api.modules.assessment.profiles import ExamProfileVersion

    version = db.get(ExamProfileVersion, version_id)
    if version is None:
        raise NotFound("Profile version not found.")
    rules = version.rules
    question_pool = rules.get("question_pool", "mock")
    sections = rules.get("sections", [])
    pools = [(int(s["questions"]), mocks._section_pool(db, s["subject"], s["grades"], question_pool)) for s in sections]
    shortages = [
        {"subject": s["subject"], "grades": s["grades"], "required": n, "available": len(p)}
        for s, (n, p) in zip(sections, pools, strict=True)
        if len(p) < n
    ]
    if shortages:
        return version, shortages, []
    try:
        chosen = mocks.select_sections(pools, set(), seed)
    except mocks.SectionShortage as e:
        s = sections[e.section - 1]
        return version, [{"subject": s["subject"], "grades": s["grades"], "required": int(s["questions"])}], []
    picks = []
    for s, (section_picks, _) in zip(sections, chosen, strict=True):
        picks += [(s, p) for p in section_picks]
    return version, [], picks


def form(db: Session, version_id: uuid.UUID, seed: int | None) -> dict[str, Any]:
    seed = seed if seed is not None else secrets.randbits(62)
    version, shortages, picks = _sample(db, version_id, seed)
    items = []
    for position, (section, (family, item, cv, option_ids)) in enumerate(picks, start=1):
        body = cv.body
        options = {o["id"]: o for o in body["options"]}
        stem_old, n_stem = _oldest(body["stem"])
        option_views, n_opt = [], 0
        for oid in option_ids:
            blocks_old, n = _oldest(options[oid]["blocks"])
            n_opt += n
            option_views.append({"id": oid, "blocks": blocks_old})
        items.append(
            {
                "position": position,
                "section": f"{section['subject']} {'+'.join(str(g) for g in section['grades'])}",
                "item_id": str(item.id),
                "version_id": str(cv.id),
                "family_id": str(family),
                "learner": {
                    "stem": body["stem"],
                    "options": [{"id": oid, "blocks": options[oid]["blocks"]} for oid in option_ids],
                },
                "oldest_client": {"stem": stem_old, "options": option_views, "fallback_blocks": n_stem + n_opt},
                "checks": checks(body),
            }
        )
    return {
        "version_id": str(version.id),
        "version": version.version,
        "status": version.status,
        "seed": seed,
        "shortages": shortages,
        "items": items,
    }


def answers(db: Session, version_id: uuid.UUID, seed: int) -> dict[str, Any]:
    """The protected answer report for the same sample (same seed)."""
    _, shortages, picks = _sample(db, version_id, seed)
    return {
        "seed": seed,
        "shortages": shortages,
        "answers": [
            {
                "position": n,
                "item_id": str(item.id),
                "correct_option_id": cv.body["correct_option_id"],
                "explanation": cv.body.get("explanation", {}),
            }
            for n, (_, (_, item, cv, _)) in enumerate(picks, start=1)
        ],
    }
