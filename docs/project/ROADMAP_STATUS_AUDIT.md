# Roadmap status audit, unregistered tasks (2026-10-12)

**What this is:** 65 roadmap tasks had no row of their own in `IMPLEMENTATION_REGISTER.md`. Each was checked against the records (`DECISIONS.md`, the register) and the code and tests. The search was by task ID, decision ID and behaviour.

For the tasks marked **Implemented**, the cited tests were confirmed to exist. They are now registered.

**This is a guide, not a gate.** "Partial" and "Blocked" say what was found and what is missing. They are not acceptance results. A task moves to the register only with its own evidence.

**Totals:** 6 implemented · 30 partial · 26 blocked on external inputs · 3 not started. Since this audit, W08.S2.T2 and P05.S4.T2 have been done (WRITTEN-INJECTION-01, REGION-01).

## Implemented (now registered)

| Task | Evidence |
| --- | --- |
| W01.S2.T3 Independent rubric versioning | IMPL-14, IMPL-19, ADJ-01; `test_content_workflow.py::test_independent_review_is_enforced`, `::test_publisher_who_edited_cannot_publish`; `test_rubric_adjudication.py::test_a_changed_scoring_basis_goes_to_a_teacher_never_a_machine_overwrite`. Academic approval itself needs B01. |
| W02.S2.T1 Client/server schemas | `packages/contracts` (OpenAPI and generated types, drift-checked in CI); CLIENTS-01 `test_client_policy.py::test_an_app_below_the_enforced_minimum_is_told_to_update`; `test_evidence.py` file validation |
| W02.S2.T2 Receipt/job transactions | IMPL-20, ALLOC-01/02, PUB-01, AUTOASSESS-01; `test_written_attempts.py::test_seal_requires_completeness_and_returns_one_receipt`; `test_publication_integrity.py::test_a_stale_lease_gets_a_recoverable_conflict`; `test_evidence.py::test_orphan_sweep_removes_only_old_unreferenced_objects` |
| W02.S2.T3 Privacy/academic boundaries | WRITTEN-AUTHZ-01, WRITTEN-INJECTION-01, ADJ-01; `test_written_authz.py`, `test_written_injection.py` |
| W05.S2.T1 Constrained assessor inputs | AUTOASSESS-01; `test_written_automatic.py::test_fixture_proposal_is_validated_bound_to_evidence_and_never_published`, `::test_invalid_or_uncertain_outputs_never_become_proposals`. Contract level only: a real provider prompt waits on B10. |
| W05.S2.T2 Validate arithmetic | `validate_output` and the shared award check; `test_written_automatic.py::test_invalid_or_uncertain_outputs_never_become_proposals`; `test_written_marking.py::test_awards_must_follow_the_rubric` |

## Partial, with what is missing

| Task | Found | Missing |
| --- | --- | --- |
| W00.S1.T1 Freeze outcomes/exclusions | SCOPE-01, D01, launch manifest | R1/R2 distinction and the tutoring, proctoring and entrance-test exclusions; owner freeze (WA-D12) |
| W00.S3.T1 Release evidence R0–R3 | Release checklist (R2 line), READINESS-01 | An R0–R3 capability and gate map |
| W00.S3.T2 Policy defaults with owners | Defaults spread across IMPL-20, RECHECK-01, RESCAN-01, ALLOC-01, ACCESS-01 | A WA-D01–D15 register with approval state; capture (WA-D13), retention (WA-D10/B15) and severe-error (WA-D06) defaults |
| W00.S3.T3 Dependency-based estimate | `DEPENDENCIES.md` waves | Estimates; the final one needs spikes (B10) |
| W01.S1.T1 Question taxonomy | IMPL-19 short/long, subparts, maxima, languages, structures | Numerical/derivation types; written passages and diagrams |
| W01.S1.T3 Publish only reviewed | IMPL-14/19 publication gate | Outcome mapping required for written items; academic approval (B01) |
| W01.S2.T1 Bounded criteria | `validate_rubric`, `reconcile` | A dependency-cycle and unreachable-credit check (only self-dependency is caught) |
| W01.S2.T2 Alternative/consequential marking | Alternative groups, dependencies, rubric checklist; teacher escalation to academic review (ACADEMIC-REVIEW-01) | Significant-figure, multiple-final-answer and contradiction rules per approved rubric (academic input, B01) |
| W02.S1.T1 Evidence/attempt model | Hashes, logical pages, frozen forms, receipts, rescans | Retention/deletion references (B15) |
| W02.S1.T2 Assessment/review provenance | Score versions, effective adjudication sets, separate assessor proposals | Reading alternatives (B10); an explicit human-protection marker |
| W02.S1.T3 Allowance/operational state | ALLOC-01, ADMIT-01, IMPL-22 | A mixed pending-and-unavailable completeness state and a zero denominator (pending currently wins) |
| W03.S1.T2 Native capture/import | NATIVE-W01 | Offline draft queue, native PDF picker, low-storage state; device proof (B14) |
| W03.S1.T4 Progressive upload, capture policy | Uploads open until U with per-file states; capture policy pinned per form | A resolution preset with a higher-detail fallback; phone qualification (B09/B14) |
| W03.S3.T3 Interruption/concurrency | Revision concurrency, deduplication, idempotent seal and rescans; weak-network retry, restart and two-tab tests (UPLOAD-RETRY-01, INTERRUPTIONS-01) | Native on a device (B14) |
| W05.S2.T3 Route unsupported reasoning | Unlisted-method and diagram flags go to review, never a mark; academic review cases (ACADEMIC-REVIEW-01) | Automatic detection needs a provider (B10) |
| W05.S3.T1 Retries/reconciliation | Stage records, backoff, dead letter and requeue | Tests for `reconcile()` and stale-lease reclaim |
| W05.S3.T2 Publication fence/provenance | No AI publication path; assessor, version, contract, hashes and latency recorded | Cost and configuration hash; the fenced writer waits on WG10/B10 |
| W05.S3.T3 Controlled failure | Malformed, duplicate, timeout and unavailable injected | An unexpected model-version change; proof that MCQ work is unaffected |
| W06.S3.T3 Train/qualify reviewers | CALIBRATION-01 | Discussion threads, periodic rounds, override and upheld-appeal audit; approved examples (B01) |
| W07.S1.T3 Answer-release policies | Rubrics never shown in attempts; MCQ release (OCT9-01) | A versioned written model-answer release |
| W07.S2.T2 Score/attempt history | Released-version history, notices, linked attempts; marking-guide and evidence versions, per-question reasons and labels (HISTORY-01) | Device check only |
| W07.S3.T2 Interrupted processing journeys | Unfinished tests across devices; idempotent notices; receipt restore after logout and on a second device (INTERRUPTIONS-01) | A native restart on a device (B09, B14) |
| W08.S1.T1 Assessment plans | Weights, page caps, units shown before start, pilot entitlements; the R0 pilot switch (PILOT-R0-01) | Cost-backed units (WA-D07) |
| P07.S3.T3 Low-bandwidth alternatives | Data saver defers diagrams; per-lesson download size (LESSON-SIZE-01) | Audio-only assets (B05) |
| P11.S3.T1 Practice configuration | Every scope, multi-subject, feedback modes, counts and shortage; topics and a measured time estimate on web and mobile (PRACTICE-CONFIG-01) | Device check only |
| P13.S4.T2 OTA update behaviour | CLIENTS-01 minimums and mock-window protection | `expo-updates` runtime-version pinning; store builds (B07) |
| P19.S2.T3 Manual accessibility | Automated axe, text size, reduced motion, captions | A manual screen-reader and 200 % zoom review by a person |
| P19.S3.T4 Content compatibility | Oldest-client and pack-format tests; the AC47 scenario and online-only pack counts (CONTENT-COMPAT-01) | An old build on a device (B07, B09, B13) |
| P19.S4.T3 Freeze release candidate | RELEASE-01 manifest; app IDs, content-release ID, rollout snapshot and known limitations (RELEASE-CANDIDATE-01) | Image digests (B03) and native builds (B07) |

## Blocked on external inputs

| Blocker | Tasks |
| --- | --- |
| Owner material, reviewers, academic decisions (B01, B02, WA-D01, WA-D12, WA-D15) | W00.S1.T2, W00.S1.T3, W00.S2.T1, W00.S2.T3, W01.S1.T2, W07.S3.T3, P05.S4.T1 |
| Real scripts, processor approval, provider spikes (B10, WA-D14) | W00.S2.T2, W00.S2.T4, W01.S3.T1, W01.S3.T2, W01.S3.T3, W02.S3.T1, W02.S3.T3, W08.S2.T3 |
| Hosting and storage (B03) | W02.S3.T2 |
| Retention and deletion policy (B15) | W08.S3.T1, W08.S3.T2, W08.S3.T3, P04.S4.T1 (legal review of guardian consent) |
| Devices, stores (B07, B09, B13, B14) | P13.S4.T1, P13.S4.T3, P19.S2.T2 |
| Search terms and benchmark queries (B16) | P11.S2.T4 |
| Invited users and a deployment | P19.S4.T1, P19.S4.T2 |

## Not started

- **W04.S1.T4, W07.S1.T4** (composite board results, R3): large; need WA-D15 and verified board patterns (B02).
- **W07.S3.T1** (written reading and navigation tests): done (WRITTEN-A11Y-01); equations and a manual screen-reader review remain.
