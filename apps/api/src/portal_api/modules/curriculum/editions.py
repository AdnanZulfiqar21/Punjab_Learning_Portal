"""Which textbook edition a calendar day uses (roadmap P05.S1.T3).

`effective_from` is inclusive and `effective_until` is exclusive. Both empty means the edition applies on every day.
That is how the imported books behave until someone records a boundary. This module does not choose a real edition year.
"""

from __future__ import annotations

from datetime import date


def covers(start: date | None, end: date | None, day: date) -> bool:
    started = start is None or day >= start
    still_open = end is None or day < end
    return started and still_open
