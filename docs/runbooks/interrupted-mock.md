# Interrupted mock exam

**Owner:** support (first line); academic operations for remedies.
**Rehearsal:** `apps/api/tests/test_mocks.py::test_rehearsal_interrupted_mock`.

**Scope today:** self-started timed mocks built from a published exam profile (MOCK-01). Scheduled mock windows,
late entry and delayed solution release (P09.S2.T3) are not built yet. No official profile is published until two
reviewers verify it (B02).

## What the system already guarantees (no staff action needed)

- Every answer is saved to the server as it is chosen. A lost connection loses nothing already acknowledged.
- Reopening the mock within its time resumes the **same** attempt, with saved answers and the original deadline.
- If the learner returns after the cutoff, the server finalises the attempt at the cutoff. Every answer saved before
  then counts, and the result is available straight away.
- The learner can always start a fresh mock (a new form). The interrupted attempt stays in their history.

## Steps when a learner reports an interruption

1. **Open the request.** In **Support → Find a learner**, check the timeline for "Practice test started" and
   "finished". "How" is `expiry` when the server finalised it at the cutoff.
2. **Confirm from server evidence**, not the learner's screen.
   - The submission receipt shows how many answers were saved.
   - The answers' save times show when activity stopped.
   - Operator signals (`/v1/ops/signals`) show whether there was a service incident at that time.
3. **No service fault:** explain that saved answers counted and that a fresh mock can be taken now.
4. **Service fault** (outage, failed saves): record it as an incident and tell the learner.
   - Mocks currently have no allowance or charge to restore, and the result stays in their history.
   - Any future paid or limited mock credit must be a separate, idempotent remedy event, never an edited result.
5. **Resolve** the request.

## Not yet covered

- Reschedule and accommodation rules for scheduled windows (P09.S2.T3).
- Who can authorise a re-sit of a ranked or scheduled mock.
