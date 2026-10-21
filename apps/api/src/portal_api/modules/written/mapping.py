"""Answer mapping helpers shared by the learner and reviewer views (W03.S2.T2, REGION-MAP-01).

Pure functions over a stored manifest and its pages, so review code can use them without the attempt service."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from portal_api.modules.written import evidence
from portal_api.modules.written.models import WrittenPage


def ambiguous_pages(slots: dict[str, dict[str, Any]]) -> list[str]:
    """REGION-MAP-01 (W03.S2.T2): pages used by more than one answer where at least one of those answers doesn't mark
    its area on the page. A teacher can't tell from the mapping which part of such a page answers which question, so
    the learner confirms that the question numbers are written on it before submitting."""
    users: dict[str, list[str]] = defaultdict(list)
    for key, slot in slots.items():
        for pid in slot.get("pages", []):
            users[pid].append(key)
    out = []
    for pid, keys in users.items():
        if len(keys) < 2:
            continue
        if any(not any(r.get("page") == pid for r in slots[k].get("regions", [])) for k in keys):
            out.append(pid)
    return sorted(out)


def manifest_view(manifest: dict[str, Any], pages: list[WrittenPage]) -> dict[str, Any]:
    """The manifest as clients see it: each marked area also as `box`, its place on the page as currently shown (the
    page's turn and trim applied), and the pages whose numbering still needs confirming as `ambiguous`."""
    transforms = {str(p.id): p.transform or {} for p in pages}
    slots: dict[str, Any] = {}
    for key, slot in manifest.get("slots", {}).items():
        regions = []
        for r in slot.get("regions", []):
            try:
                box = evidence.from_source(r["source"], transforms.get(r["page"]))
            except (evidence.Rejected, KeyError, TypeError, ValueError):
                box = None
            regions.append({**r, "box": [round(v, 4) for v in box] if box else None})
        slots[key] = {**slot, "regions": regions}
    ambiguous = ambiguous_pages(manifest.get("slots", {}))
    confirmed = set(manifest.get("confirmed", []))
    return {
        **manifest,
        "slots": slots,
        "confirmed": [p for p in ambiguous if p in confirmed],
        "ambiguous": [p for p in ambiguous if p not in confirmed],
    }


def ordered_pages(pages: list[WrittenPage], manifest: dict[str, Any]) -> list[WrittenPage]:
    """REGION-MAP-01: pages in the learner's order (`order` in the manifest); pages it doesn't list follow in upload
    order."""
    rank = {pid: i for i, pid in enumerate(manifest.get("order", []))}
    return sorted(pages, key=lambda p: (rank.get(str(p.id), len(rank)),))
