"""Expiry worker (P10.S1.T2): finalise attempts whose admission cutoff C has passed.

    portal-expire-attempts            # one pass; schedule it every few seconds in each environment

Attempts are also finalised lazily under their lock whenever they are read or written after C, so a delayed worker
never lets a late write in; the worker only makes results appear without the learner returning.
"""

from __future__ import annotations

import sys

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment.attempts import expire_due
from portal_api.modules.written.service import expire_due as expire_written


def main(argv: list[str] | None = None) -> int:
    with get_sessionmaker()() as db:
        done = expire_due(db)
        written = expire_written(db)  # unsealed written scripts past U; never partially sealed
    print(f"expired {done} MCQ attempt(s) and {written} written attempt(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
