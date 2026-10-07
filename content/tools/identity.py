"""Stable identity for catalogue entities across index corrections (decision IMPL-08).

The committed ID registry (content/catalogue/id_registry.json) is the authority for which academic entity an ID
denotes. A rebuild reconciles freshly built entities with the registry instead of deriving IDs from mutable text, so
correcting a heading title, a printed number or a numbered/unnumbered classification keeps the same ID.

Matching order for each new entity, within its parent (book for chapters, chapter for topics):
  1. explicit override   (content/catalogue/id_overrides.json: natural_key -> id, reviewer-confirmed remaps)
  2. same natural key or a recorded alias of an existing entity
  3. same printed number (topics/chapters that carry one)
  4. same normalised title, then title similarity >= TITLE_SIMILARITY
  5. otherwise a new ID (UUIDv5 of the natural key, de-duplicated against the registry)
Existing entities that nothing matched are RETIRED (kept with retired_on + reason), never deleted; a later rebuild
that matches them again reactivates the same ID.
"""

from __future__ import annotations

import difflib
import re
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date
from typing import Any

TITLE_SIMILARITY = 0.85
REGISTRY_SCHEMA = 1


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


@dataclass
class Stats:
    by_override: int = 0
    by_key: int = 0
    by_number: int = 0
    by_title: int = 0
    new: int = 0
    retired: int = 0
    reactivated: int = 0
    changes: list[str] = field(default_factory=list)


def empty_registry() -> dict[str, Any]:
    return {"schema_version": REGISTRY_SCHEMA, "entities": {}}


def _walk_topics(topics: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for t in topics:
        yield t
        yield from _walk_topics(t.get("children") or [])


def reconcile(
    books: list[dict[str, Any]],
    registry: dict[str, Any],
    overrides: dict[str, str],
    new_id: Callable[[str], str],
    today: str | None = None,
) -> Stats:
    """Assign stable IDs in place on `books` (chapters and topics) and update `registry`. Returns statistics."""
    today = today or date.today().isoformat()
    ents: dict[str, dict[str, Any]] = registry.setdefault("entities", {})
    stats = Stats()

    def assign(kind: str, parent_id: str, item: dict[str, Any], claimed: set[str]) -> str:
        key = item["natural_key"]
        candidates = {i: e for i, e in ents.items() if e["kind"] == kind and e["parent"] == parent_id and i not in claimed}
        chosen: str | None = None
        how = ""
        if key in overrides:
            chosen, how = overrides[key], "override"
        if chosen is None:
            for i, e in candidates.items():
                if e["key"] == key or key in e.get("aliases", []):
                    chosen, how = i, "key"
                    break
        number = item.get("number")
        if chosen is None and number not in (None, ""):
            same = [i for i, e in candidates.items() if e.get("number") == number]
            if len(same) == 1:
                chosen, how = same[0], "number"
        if chosen is None:
            nt = norm_title(item.get("title", ""))
            exact = [i for i, e in candidates.items() if norm_title(e.get("title", "")) == nt]
            if len(exact) == 1:
                chosen, how = exact[0], "title"
            else:
                scored = sorted(
                    ((difflib.SequenceMatcher(None, nt, norm_title(e.get("title", ""))).ratio(), i) for i, e in candidates.items()),
                    reverse=True,
                )
                if scored and scored[0][0] >= TITLE_SIMILARITY and (len(scored) == 1 or scored[1][0] < scored[0][0]):
                    chosen, how = scored[0][1], "title"
        if chosen is None:
            chosen = new_id(key)
            n = 2
            while chosen in ents:  # never reuse an ID that already denotes another entity
                chosen = new_id(f"{key}#{n}")
                n += 1
            how = "new"
        claimed.add(chosen)
        prev = ents.get(chosen)
        if prev is None:
            ents[chosen] = {"kind": kind, "parent": parent_id, "key": key, "aliases": [], "number": number,
                            "title": item.get("title", ""), "status": "active", "first_seen": today}
            stats.new += 1
        else:
            if prev["key"] != key:
                prev.setdefault("aliases", [])
                if prev["key"] not in prev["aliases"]:
                    prev["aliases"].append(prev["key"])
                stats.changes.append(f"{kind} {chosen}: key {prev['key']} -> {key} (matched by {how})")
                prev["key"] = key
            for attr in ("number", "title"):
                if prev.get(attr) != item.get(attr):
                    stats.changes.append(f"{kind} {chosen}: {attr} {prev.get(attr)!r} -> {item.get(attr)!r}")
                    prev[attr] = item.get(attr)
            prev["parent"] = parent_id
            if prev.get("status") == "retired":
                prev["status"] = "active"
                prev.pop("retired_on", None)
                prev.pop("retired_reason", None)
                stats.reactivated += 1
            setattr(stats, f"by_{how}", getattr(stats, f"by_{how}") + 1)
        item["id"] = chosen
        return chosen

    for book in books:
        claimed_chapters: set[str] = set()
        for ch in book["chapters"]:
            ch_id = assign("chapter", book["id"], ch, claimed_chapters)
            claimed_topics: set[str] = set()
            for t in _walk_topics(ch["topics"]):
                assign("topic", ch_id, t, claimed_topics)
            _retire(ents, "topic", ch_id, claimed_topics, today, stats)
        _retire(ents, "chapter", book["id"], claimed_chapters, today, stats)
    # Topics of a retired chapter are retired with it.
    retired_chapters = {i for i, e in ents.items() if e["kind"] == "chapter" and e.get("status") == "retired"}
    for chapter_id in retired_chapters:
        _retire(ents, "topic", chapter_id, set(), today, stats)
    return stats


def _retire(ents: dict[str, dict[str, Any]], kind: str, parent: str, keep: set[str], today: str, stats: Stats) -> None:
    for i, e in ents.items():
        if e["kind"] == kind and e["parent"] == parent and i not in keep and e.get("status") != "retired":
            e["status"] = "retired"
            e["retired_on"] = today
            e["retired_reason"] = "no longer present in the source index after reconciliation"
            stats.retired += 1
            stats.changes.append(f"{kind} {i}: retired ({e['key']})")


def default_new_id(namespace: uuid.UUID) -> Callable[[str], str]:
    return lambda key: str(uuid.uuid5(namespace, key))
