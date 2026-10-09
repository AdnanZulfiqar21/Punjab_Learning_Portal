"""Time-budgeted study plan (roadmap P12.S4.T1, §6.6 infeasible deadlines; STUDYPLAN-01).

* **Required minutes:** each topic of the chosen book needs estimated remaining work by evidence state:
  `demonstrated` 0, `developing` `DEVELOPING_MINUTES`, `insufficient_evidence` `NO_EVIDENCE_MINUTES`. Missing
  evidence uses the cold-start rule (syllabus order), never an invented zero ability.
* **Available minutes:** whole days from today to the target date, times the learner's daily minutes.
* **Priority:** weakest evidence first. Developing topics with low independent accuracy come first, then other
  developing topics, then topics without evidence. Ties follow the book's chapter and topic order, which serves as
  the prerequisite order until a verified prerequisite map exists.
* **Infeasible:** if required exceeds available, the shortfall is shown and only the highest-priority work that fits
  is scheduled. The plan never implies everything will be completed.

The plan is recomputed from current evidence each time, so a missed day simply replans; there is no backlog of guilt.
It never alters an official-pattern mock and never predicts admission. The minute estimates are transparent initial
product defaults.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

DEVELOPING_MINUTES = 30
NO_EVIDENCE_MINUTES = 45
MIN_DAILY = 10


def build(outcomes: list[dict[str, Any]], *, today: date, target: date, daily_minutes: int) -> dict[str, Any]:
    """`outcomes` in book order, each with outcome_id, label, chapter_number, state and independent_accuracy."""
    days = (target - today).days
    available = max(days, 0) * daily_minutes

    def need(o: dict[str, Any]) -> int:
        return {"demonstrated": 0, "developing": DEVELOPING_MINUTES}.get(o["state"], NO_EVIDENCE_MINUTES)

    def rank(i_o: tuple[int, dict[str, Any]]) -> tuple[int, float, int]:
        i, o = i_o
        if o["state"] == "developing":
            acc = o.get("independent_accuracy")
            return (0, acc if acc is not None else 1.0, i)
        return (1, 0.0, i)

    work = [(i, o) for i, o in enumerate(outcomes) if need(o) > 0]
    required = sum(need(o) for _, o in work)
    ordered = [o for _, o in sorted(work, key=rank)]
    schedule: list[dict[str, Any]] = []
    day, left = 0, daily_minutes
    for o in ordered:
        m = need(o)
        if day >= days:
            break
        if m > left:  # start the topic on the next day rather than splitting it
            day, left = day + 1, daily_minutes
            if day >= days:
                break
        schedule.append(
            {
                "date": (today + timedelta(days=day)).isoformat(),
                "outcome_id": str(o["outcome_id"]),
                "label": o["label"],
                "chapter_number": o["chapter_number"],
                "minutes": m,
                "why": "Developing: practise and review"
                if o["state"] == "developing"
                else "No evidence yet: learn and practise",
            }
        )
        left -= m
    scheduled = sum(x["minutes"] for x in schedule)
    return {
        "today": today.isoformat(),
        "target_date": target.isoformat(),
        "days": max(days, 0),
        "daily_minutes": daily_minutes,
        "required_minutes": required,
        "available_minutes": available,
        "shortfall_minutes": max(required - available, 0),
        "feasible": required <= available,
        "scheduled_minutes": scheduled,
        "unscheduled_topics": len(ordered) - len(schedule),
        "schedule": schedule,
        "assumptions": {
            "developing_minutes": DEVELOPING_MINUTES,
            "no_evidence_minutes": NO_EVIDENCE_MINUTES,
            "order": "weakest evidence first, then the book's chapter and topic order",
        },
    }


def outcome_rows(evidence_report: Any) -> list[dict[str, Any]]:
    return [
        {
            "outcome_id": uuid.UUID(str(o.outcome_id)),
            "label": o.label,
            "chapter_number": o.chapter_number,
            "state": o.state,
            "independent_accuracy": o.independent_accuracy,
        }
        for o in evidence_report.outcomes
    ]
