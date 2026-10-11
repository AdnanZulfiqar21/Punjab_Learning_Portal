"""Studio surface report: how an item reaches each delivery surface before publication (roadmap P06.S3.T1;
SURFACES-01).

Learner web and the phone layout render the same blocks (the web preview shows both widths). This report adds what
can't be seen by looking at one client: the oldest supported app's rendering (reviewed fallbacks in place of blocks
it can't show), the item's language variants, its access tier, and everything still missing before learners can be
given it: fallbacks, fallback review, image alt text, unverifiable diagram assets and source-page mapping. Tables
always have captions and equations always have a text equivalent, because the block schema requires them.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from portal_api.modules.content import blocks
from portal_api.modules.content.models import ContentItem

LANGUAGES = ("en", "ur", "roman_ur")
ACCESS = {
    "preview": "Free sample: anyone signed in can open it.",
    "premium": "Needs an active plan or the free trial.",
}


def _groups(kind: str, body: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    def bl(v: Any) -> list[dict[str, Any]]:
        return [b for b in v if isinstance(b, dict)] if isinstance(v, list) else []

    if kind == "lesson":
        return [("Lesson", bl(body.get("blocks")))]
    if kind == "mcq":
        out = [("Question", bl(body.get("stem")))]
        out += [(f"Option {o.get('id')}", bl(o.get("blocks"))) for o in body.get("options", []) if isinstance(o, dict)]
        raw = body.get("explanation")
        explanation: dict[str, Any] = raw if isinstance(raw, dict) else {}
        return [*out, ("Explanation", bl(explanation.get("correct")))]
    if kind == "written":
        out = [("Question", bl(body.get("stem")))]
        return out + [
            (f"Part {s.get('id')}", bl(s.get("blocks"))) for s in body.get("subparts", []) if isinstance(s, dict)
        ]
    return []


def _issues(where: str, block: dict[str, Any]) -> list[str]:
    kind = str(block.get("type"))
    fb = block.get("fallback") if isinstance(block.get("fallback"), dict) else None
    out = []
    if blocks.needs_fallback(kind):
        if not fb:
            out.append(f"{where}: a {kind} block needs a reviewed fallback for the oldest supported app.")
        elif not fb.get("reviewed"):
            out.append(f"{where}: the {kind} block's fallback isn't marked as reviewed.")
    if fb and fb.get("image_asset_id"):
        if not fb.get("alt"):
            out.append(f"{where}: the fallback image has no alt text.")
        out.append(
            f"{where}: diagram asset {fb['image_asset_id']} can't be checked until the asset store exists (P07)."
        )
    return out


def report(db: Session, item: ContentItem) -> dict[str, Any]:
    version = item.working or item.published
    body = version.body if version is not None and isinstance(version.body, dict) else {}
    issues: list[str] = []
    views, total = [], 0
    for where, group in _groups(item.kind, body):
        shown, n = blocks.oldest_client(group)
        total += n
        views.append({"where": where, "blocks": shown})
        for b in group:
            issues += _issues(where, b)
    if version is not None and not version.source_refs:
        issues.append("No source pages are mapped; every published item cites its source pages.")
    languages: dict[str, Any] = {}
    if item.kind == "lesson":
        concept = item.concept_id or item.id
        present = sorted(
            set(
                db.scalars(
                    select(ContentItem.language).where(
                        or_(ContentItem.id == concept, ContentItem.concept_id == concept)
                    )
                )
            )
        )
        languages = {"present": present, "missing": [x for x in LANGUAGES if x not in present]}
    return {
        "version_id": str(version.id) if version is not None else None,
        "version_number": version.number if version is not None else None,
        "oldest_client": views,
        "fallback_blocks": total,
        "issues": issues,
        "access": {"tier": item.access_tier, "meaning": ACCESS.get(item.access_tier, "")},
        "languages": languages,
    }
