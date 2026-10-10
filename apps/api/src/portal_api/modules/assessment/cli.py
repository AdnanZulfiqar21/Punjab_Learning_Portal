"""Attempt worker (P10.S1.T2, P10.S3.T3): finalise attempts whose admission cutoff C has passed, and score any
submission whose scoring failed or was interrupted.

    portal-expire-attempts            # one pass; schedule it every few seconds in each environment

Attempts are also finalised lazily under their lock whenever they are read or written after C, so a delayed worker
never lets a late write in; the worker only makes results appear without the learner returning.
"""

from __future__ import annotations

import sys

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment.attempts import expire_due, score_pending
from portal_api.modules.written.service import expire_due as expire_written


def main(argv: list[str] | None = None) -> int:
    with get_sessionmaker()() as db:
        done = expire_due(db)
        written = expire_written(db)  # unsealed written scripts past U; never partially sealed
        scored = score_pending(db)  # P10.S3.T3: submissions whose scoring failed or was interrupted
    print(f"expired {done} MCQ attempt(s) and {written} written attempt(s); scored {scored} pending attempt(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
