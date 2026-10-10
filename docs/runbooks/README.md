# Incident runbooks (P15.S4.T3)

Staff resolve common incidents with the documented tools below, never with manual database edits. Every step listed is
audited. Each runbook is rehearsed by an automated test that walks the same steps against the real API.

| Incident | Runbook | Rehearsal | Status |
|---|---|---|---|
| Learner paid but has no access | [missing-access.md](missing-access.md) | `apps/api/tests/test_incident_rehearsals.py::test_rehearsal_missing_paid_access` | Rehearsed. Interim remedy only: payments are not live (B06). |
| Trial refused on a shared or second-hand device | [trial-false-block.md](trial-false-block.md) | `test_rehearsal_trial_false_block_appeal` | Rehearsed. The rehearsal found and fixed a gap: an exception did not help a brand-new account. |
| Disputed question (soft, then void) | [disputed-question.md](disputed-question.md) | `apps/api/tests/test_mcq_corrections.py::test_rehearsal_disputed_question_soft_then_void` | Rehearsed: SOFT, then VOID with re-scoring as new score versions (§5.7). |
| Interrupted mock exam | [interrupted-mock.md](interrupted-mock.md) | `apps/api/tests/test_mocks.py::test_rehearsal_interrupted_mock`; scheduled windows: `test_mock_deadlines.py` | Rehearsed for self-started mocks (MOCK-01). Scheduled windows exist (SCHEDULE-01, OCT9-04): staff can move `results_at` later and grant accommodations within it. |
| Compromised account or leaked secret | [compromised-account-or-secret.md](compromised-account-or-secret.md) | `test_account_suspension.py::test_suspension_is_immediate_scoped_and_reversible` | Account suspension rehearsed; secret rotation waits on the hosting secret store (B03). |
| Result shows "scoring pending" | [scoring-pending.md](scoring-pending.md) | `test_scoring_recovery.py` | Rehearsed (RECOVERABLE-SCORING-01). |
| Operator alerts (queues, errors, latency, pool) | [alerts.md](alerts.md) | `test_operations.py`, `test_service_overview.py` | Signals and thresholds tested; paging waits on hosting (B03). |

Shared rules:

- Sign in with multi-factor authentication. Lookups, timelines, exceptions, grants and quarantine all require it.
- Find the learner only by the exact email they used (**Support → Find a learner**). Never ask for passwords, CNIC or card numbers.
- Write a reason on every action and cite the help request ID.
- Never promise a corrected answer or score before an approved adjudication is recorded.
- Escalate (**Escalate** on the request) when a step needs finance, an academic adjudicator or the owner.

Not written yet, because the systems they cover don't exist: database/media restore and provider outages (B03–B05), payment callback backlog (B06) and attestation outage (B07/B08).
