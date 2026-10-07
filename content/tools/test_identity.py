"""Stable catalogue identity (IMPL-08): corrections keep IDs; removals retire; ambiguity never merges wrongly."""

from __future__ import annotations

import copy
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from identity import default_new_id, empty_registry, reconcile  # noqa: E402

NEW_ID = default_new_id(uuid.UUID("00000000-0000-0000-0000-000000000001"))


def topic(key: str, number: str | None, title: str, children: list | None = None) -> dict:
    return {"id": None, "natural_key": f"book/ch5/{key}", "number": number, "title": title, "children": children or []}


def book(topics: list[dict]) -> list[dict]:
    return [{"id": "book-1", "chapters": [{"id": None, "natural_key": "book/ch5", "number": 5, "title": "Enzymes",
                                          "topics": topics}]}]


def ids(books: list[dict]) -> dict[str, str]:
    out = {}

    def walk(ts):
        for t in ts:
            out[t["title"]] = t["id"]
            walk(t["children"])

    for b in books:
        for ch in b["chapters"]:
            out["__chapter__"] = ch["id"]
            walk(ch["topics"])
    return out


def first_build():
    reg = empty_registry()
    base = book([topic("5.1", "5.1", "Characteristics of Enzymes"), topic("5.2", "5.2", "Mechanism of Enzyme Action"),
                 topic("u-intro", None, "Introduction"), topic("5.3", "5.3", "Factors Affecting Enzyme Activity")])
    reconcile(base, reg, {}, NEW_ID, today="2026-10-01")
    return reg, ids(base)


def rebuild(reg, topics, overrides=None):
    b = book(topics)
    stats = reconcile(b, reg, overrides or {}, NEW_ID, today="2026-10-07")
    return ids(b), stats


def test_title_correction_keeps_id():
    reg, before = first_build()
    after, stats = rebuild(reg, [topic("5.1", "5.1", "Characteristics of Enzymes (corrected)"),
                                 topic("5.2", "5.2", "Mechanism of Enzyme Action"), topic("u-intro", None, "Introduction"),
                                 topic("5.3", "5.3", "Factors Affecting Enzyme Activity")])
    assert after["Characteristics of Enzymes (corrected)"] == before["Characteristics of Enzymes"]
    assert stats.new == 0 and stats.retired == 0


def test_printed_number_correction_keeps_id():
    reg, before = first_build()
    after, _ = rebuild(reg, [topic("6.1", "6.1", "Characteristics of Enzymes"), topic("6.2", "6.2", "Mechanism of Enzyme Action"),
                             topic("u-intro", None, "Introduction"), topic("6.3", "6.3", "Factors Affecting Enzyme Activity")])
    for t in ("Characteristics of Enzymes", "Mechanism of Enzyme Action", "Factors Affecting Enzyme Activity"):
        assert after[t] == before[t]
    entity = reg["entities"][before["Characteristics of Enzymes"]]
    assert entity["number"] == "6.1" and "book/ch5/5.1" in entity["aliases"]


def test_numbered_unnumbered_toggle_keeps_id():
    reg, before = first_build()
    after, _ = rebuild(reg, [topic("5.1", "5.1", "Characteristics of Enzymes"), topic("5.2", "5.2", "Mechanism of Enzyme Action"),
                             topic("5.0", "5.0", "Introduction"), topic("5.3", "5.3", "Factors Affecting Enzyme Activity")])
    assert after["Introduction"] == before["Introduction"]


def test_removed_topic_is_retired_and_reactivated_with_same_id():
    reg, before = first_build()
    _, stats = rebuild(reg, [topic("5.1", "5.1", "Characteristics of Enzymes"), topic("5.2", "5.2", "Mechanism of Enzyme Action"),
                             topic("5.3", "5.3", "Factors Affecting Enzyme Activity")])
    gone = reg["entities"][before["Introduction"]]
    assert stats.retired == 1 and gone["status"] == "retired" and gone["retired_on"] == "2026-10-07"
    again, stats2 = rebuild(reg, [topic("5.1", "5.1", "Characteristics of Enzymes"), topic("5.2", "5.2", "Mechanism of Enzyme Action"),
                                  topic("u-intro", None, "Introduction"), topic("5.3", "5.3", "Factors Affecting Enzyme Activity")])
    assert again["Introduction"] == before["Introduction"] and stats2.reactivated == 1
    assert reg["entities"][before["Introduction"]]["status"] == "active"


def test_explicit_override_wins():
    reg, before = first_build()
    after, stats = rebuild(
        reg,
        [topic("5.1", "5.1", "Characteristics of Enzymes"), topic("5.2", "5.2", "Mechanism of Enzyme Action"),
         topic("u-overview", None, "Chapter overview"), topic("5.3", "5.3", "Factors Affecting Enzyme Activity")],
        overrides={"book/ch5/u-overview": before["Introduction"]},
    )
    assert after["Chapter overview"] == before["Introduction"] and stats.by_override == 1


def test_ambiguous_or_unrelated_headings_get_new_ids_not_wrong_merges():
    reg, before = first_build()
    after, stats = rebuild(reg, [topic("5.1", "5.1", "Characteristics of Enzymes"), topic("5.2", "5.2", "Mechanism of Enzyme Action"),
                                 topic("u-intro", None, "Introduction"), topic("5.3", "5.3", "Factors Affecting Enzyme Activity"),
                                 topic("u-new", None, "Enzyme Kinetics Graphs")])
    assert after["Enzyme Kinetics Graphs"] not in before.values() and stats.new == 1
    assert len(set(after.values())) == len(after)


def test_chapter_removal_retires_its_topics():
    reg, before = first_build()
    reconcile([{"id": "book-1", "chapters": []}], reg, {}, NEW_ID, today="2026-10-07")
    assert all(reg["entities"][i]["status"] == "retired" for i in before.values())


def test_reconcile_is_idempotent():
    reg, before = first_build()
    snapshot = copy.deepcopy(reg)
    after, stats = rebuild(reg, [topic("5.1", "5.1", "Characteristics of Enzymes"), topic("5.2", "5.2", "Mechanism of Enzyme Action"),
                                 topic("u-intro", None, "Introduction"), topic("5.3", "5.3", "Factors Affecting Enzyme Activity")])
    assert after == before and stats.changes == [] and reg == snapshot
