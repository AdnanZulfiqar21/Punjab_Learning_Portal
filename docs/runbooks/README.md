# Incident runbooks (P15.S4.T3)

Staff resolve common incidents with the documented tools below, never with manual database edits. Every step listed is
audited. Each runbook is rehearsed by an automated test that walks the same steps against the real API.

| Incident | Runbook | Rehearsal | Status |
|---|---|---|---|
| Learner paid but has no access | [missing-access.md](missing-access.md) | `apps/api/tests/test_incident_rehearsals.py::test_rehearsal_missing_paid_access` | Rehearsed. Interim remedy only: payments are not live (B06). |
| Trial refused on a shared or second-hand device | [trial-false-block.md](trial-false-block.md) | `test_rehearsal_trial_false_block_appeal` | Rehearsed. The rehearsal found and fixed a gap: an exception did not help a brand-new account. |
| Disputed question (soft, then void) | [disputed-question.md](disputed-question.md) | Soft: `tests/test_attempts.py::test_forms_are_frozen_idempotent_and_exclude_quarantined` | Soft quarantine works. **Void/key-error score propagation (§5.7) is not built yet**; it is the next task. |
| Interrupted mock exam | [interrupted-mock.md](interrupted-mock.md) | none | **Blocked**: timed mock exams are not built (P11). |

Shared rules:

- Sign in with multi-factor authentication. Lookups, timelines, exceptions, grants and quarantine all require it.
- Find the learner only by the exact email they used (**Support → Find a learner**). Never ask for passwords, CNIC or card numbers.
- Write a reason on every action and cite the help request ID.
- Never promise a corrected answer or score before an approved adjudication is recorded.
- Escalate (**Escalate** on the request) when a step needs finance, an academic adjudicator or the owner.
