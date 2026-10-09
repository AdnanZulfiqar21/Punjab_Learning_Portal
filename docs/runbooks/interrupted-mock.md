# Interrupted mock exam

**Status: blocked.** Timed full-length mock exams (roadmap P11) are not built, so there is nothing to rehearse yet.

Practice tests already handle interruptions without staff action:

- Answers are saved as they are entered.
- Reopening a test resumes the same attempt.
- Practice tests without a deadline can be finished later.
- A test with a deadline is finalised automatically at its cutoff, and every answer saved before then counts.

When mocks are built, this runbook must cover:

1. Confirming the interruption from server-side timing evidence, not the learner's screen.
2. The published retry or reschedule route, and who may authorise it.
3. Any allowance or credit remedy, recorded as a separate idempotent event.

It also needs an automated rehearsal like the other runbooks.
