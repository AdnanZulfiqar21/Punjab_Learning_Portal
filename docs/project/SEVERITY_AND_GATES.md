# Issue severity and gate rules (P00.S3.T2, SEVERITY-01)

Recorded 2026-10-21 from the roadmap: P00.S3.T2, §7.2 gate status and mandatory evidence, §13.1 release stop conditions, and acceptance case AC60. This page is a record of the rules, not an approval.

The owners named below are roles. Named people for each role are still open (G00: "named input owners"; reviewers and academic roles wait on B01).

## Severities

| Severity | Meaning | Examples (from §13.1) | Owner (role) | Release rule |
| --- | --- | --- | --- | --- |
| **P0** | Outage or data loss, or a learner harmed by a wrong or exposed result | Lost acknowledged answers, incorrect grading, exposed answer keys or private data, failed database or media recovery, overwritten human marking decisions, a submission protocol that silently drops or accepts pending answers | Engineering lead; the academic lead also owns grading and marking defects | Blocks every release until fixed and retested |
| **P1** | A critical journey is broken, with no safe workaround | Sign-up, trial, lesson reading, practice start/save/submit, results, written upload/seal/receipt, payment access, staff publish or review cannot be completed on a supported browser or device | Engineering lead, with the product owner for scope | Blocks every release until fixed and retested |
| **P2** | A journey works but is degraded, or a non-critical feature is broken | Wrong copy that does not mislead about marks or access, a slow page within budget, an admin report error | Product owner triages | Release may proceed with the defect listed as a known limitation |
| **P3** | Cosmetic or minor | Spacing, wording, an icon | Product owner triages | Does not block |

**Stop the capability, not everything (§13.1).**

- A defective question is quarantined (QUARANTINE levels, MCQADJ-01). A syllabus or profile mismatch stops only the affected exams.
- A written-assessment stop condition stops only the affected written capability and keeps accepted work.
- None of these on its own stops unrelated, qualified MCQ or learning routes.

## Where defects are recorded

`docs/project/DEFECTS.md` is the defect register: one row per P0 or P1 defect, and per P2 or P3 when it is listed as a launch limitation. The release checklist item "Zero unresolved P0/P1 defects" is read from it.

An empty register means only that nothing has been recorded. Before any release, a triage pass must record every defect found.

## Gate rules (§7.2, AC60)

- **Separate states.** Task states (`TODO` … `ACCEPTED`) and gate states (`NOT_READY`, `BLOCKED_EXTERNAL`, `BLOCKED_DECISION`, `FAILED`, `PASSED`, `INVALIDATED`) are separate. A gate row may use only gate states.
- **When a gate passes.** A gate is `PASSED` only when every mandatory check in its recorded scope has current evidence.
- **Blockers are not evidence.** A recorded blocker never counts as passing evidence. A gate whose recorded scope still names an open `BLOCKED_EXTERNAL` or `BLOCKED_DECISION` blocker cannot be `PASSED`; this is AC60's "a required billing or device check blocked".
- **Optional scope.** An optional item may sit outside a gate only when the approved scope already deferred it, or when a recorded scope decision excluded it. Then it doesn't block unrelated work (AC60).
- **Material changes.** A material change after qualification sets the affected evidence to `INVALIDATED` until the required retest passes. The release-checklist tool `python -m portal_api.qualification impact` lists which records a change invalidates (QUALIFICATION-01).
- **Early G00.** Early G00 covers P00.S1–S2, the initial P00.S3.T1/T2 controls and the initial P00.S3.T4 dependency register. It can pass while the P00.S3.T3 estimate is still open. That estimate stays visibly open, closes at M1 after the real-data spikes, and is mandatory before P21.
- **Readiness states.** Platform Ready, Content Ready and Public Launch Ready can't be claimed if:
  - any of their own checklist items is unticked;
  - any blocker is open;
  - any P0 or P1 defect is open.

## Enforcement

`apps/api/tests/test_readiness_claims.py` (READINESS-01, extended by SEVERITY-01) fails CI when:

- a readiness state is claimed while one of its items is unticked, a blocker is open, or a P0 or P1 defect is open;
- `DEFECTS.md` has a row with an unknown severity or status;
- a gate row uses a state that §7.2 does not define;
- a gate row is `PASSED` while it names an open blocker.

Each check is also exercised against synthetic text, so a broken check is caught.
