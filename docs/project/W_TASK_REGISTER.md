# Written-assessment task register (W11.S3.T3)

**Task:** W11.S3.T3 "Maintain module/master continuity": one row for every written-assessment (W) task ID in the roadmap,
with its current status and evidence, and a list of stale rows in the other records. **Date:** 2026-10-21. **Base:**
`main` at `764319e2` (includes #355 region mapping, #358 qualification records and #234 container images).

**Method.**

1. Every `- [ ] **Wxx.Sy.Tz — Title**` line was extracted from
   `Road Map/Punjab_Learning_Portal_Master_Roadmap_v2.2_Integrated_Written_Assessment.md` (§20.17). There are **117**,
   which matches the roadmap's own count ("12 phases, 36 stages and 117 tasks") and the register header.
2. For each ID, these records were searched, with ranges such as `W03.S2.T2/T3`, `W04.S1.T1–T3` and `W05.S3.T2-T3`
   expanded: `IMPLEMENTATION_REGISTER.md` (Reg), `WORK_QUEUE.md` (WQ, with its class A, B, C or D),
   `ROADMAP_STATUS_AUDIT.md` (Audit), `DECISIONS.md`, `BLOCKERS.md`, `RELEASE_CHECKLIST.md`, `LAUNCH_MANIFEST.md`,
   `DEPENDENCIES.md` and `CAPACITY_BUDGET.md`.
3. Every test file cited for a W task was checked against `git ls-files`, and all of them exist. Where a record and
   the code disagreed, `apps/` was searched for the decision ID or the behaviour. For example, it was searched for
   `REGION-MAP-01`, for signed or presigned upload sessions and for reading-record code. CI results for #355 and #358
   were read with `gh pr view`.
4. Uncommitted files in the working tree that are not on `main` were not used as evidence.

**Status rule.** A blocker is never passing evidence, and no status here is higher than its cited evidence supports.
Task state is not gate state: no W gate (WG00 to WG11) has passed, and nothing here is release qualified.

- **IMPLEMENTED:** code or records, plus passing tests, deliver the task's own subpoints, at least for the stated
  slice. What remains is device, real-data or deployment verification, or an input owned by someone else.
- **PARTIAL:** part of the task's own deliverable exists. The missing part is named.
- **IN_PROGRESS:** work on the task is underway now.
- **TODO:** nothing has been built, and the next step does not need an external input.
- **BLOCKED_EXTERNAL:** nothing substantive has been built, and the next step needs a named external input: a B-number
  from BLOCKERS, a WA-D owner decision or an owner action.

## Summary

| Status | Count |
|---|---|
| IMPLEMENTED | 50 |
| PARTIAL | 18 |
| IN_PROGRESS | 1 |
| TODO | 1 |
| BLOCKED_EXTERNAL | 47 |
| **Total W task IDs** | **117** |

By phase (IMPLEMENTED / PARTIAL / IN_PROGRESS / TODO / BLOCKED_EXTERNAL):

- W00: 2 / 1 / 0 / 1 / 6
- W01: 3 / 2 / 0 / 0 / 4
- W02: 4 / 2 / 0 / 0 / 3
- W03: 6 / 4 / 0 / 0 / 0
- W04: 8 / 1 / 0 / 0 / 1
- W05: 6 / 1 / 0 / 0 / 3
- W06: 8 / 2 / 0 / 0 / 0
- W07: 8 / 0 / 0 / 0 / 2
- W08: 4 / 1 / 0 / 0 / 4
- W09: 1 / 1 / 0 / 0 / 7
- W10: 0 / 0 / 0 / 0 / 11
- W11: 0 / 3 / 1 / 0 / 6

**Register coverage:** 60 of 117 W IDs have their own `IMPLEMENTATION_REGISTER.md` row. The other 57 read as TODO under
the register's "any task not listed is TODO" rule, but the evidence below puts them at:

- 47 BLOCKED_EXTERNAL
- 8 PARTIAL: W01.S1.T3, W02.S1.T1, W02.S1.T2, W03.S1.T4, W05.S1.T4, W11.S1.T3, W11.S3.T1, W11.S3.T2
- 1 TODO: W00.S3.T3
- 1 IN_PROGRESS: W11.S3.T3

## Register

### W00 — Scope, real-data intake and release agreement

| ID | Title | Status | Evidence (register row / decision / tests) | Remaining | Blocker |
|---|---|---|---|---|---|
| W00.S1.T1 | Freeze the student outcomes and exclusions | PARTIAL | Reg `W00.S1.T1` ("RECORDED", which is not a register state); `LAUNCH_MANIFEST.md` "Written assessment: required outcomes and exclusions", marked PROPOSED; SCOPE-01, WRITTEN-SCOPE-01 | The owner's freeze of outcomes and exclusions | WA-D12 (owner) |
| W00.S1.T2 | Select the first academic slice | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked. WA-D01 interim default: "None chosen", so only technical fixture questions are used | Inventory the owner's material; choose subject, grade, chapter, language and type; publish the supported matrix | WA-D01, B01 |
| W00.S1.T3 | Approve the student-facing assessment claims | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked. English result copy exists in the product (RESULT-ARITHMETIC-01: S + P + U = M and work status; help draft `written-marking-and-results.md`), but no claims record exists and nothing is approved | A claims record for approval; Urdu copy; owner and academic approval | Owner; B01 (Urdu reviewer) |
| W00.S2.T1 | Complete source intake | BLOCKED_EXTERNAL | Reg: none, though the P22.S1 rows cover textbook intake (`content/source_registry.json`, 10 sources). WQ D; Audit: blocked; DEPENDENCIES wave B is IN_PROGRESS | Board and session references, question ownership, draft rubrics, reviewer assignments; owner acceptance | B01, B02, owner |
| W00.S2.T2 | Register real-script permissions and coverage | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked | Consented scripts; minimisation; a record of language, type, conditions and grouping | B10 |
| W00.S2.T3 | Name the operational owners | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked | Named owners for adjudication, review, providers, privacy, support and incidents, with their availability | Owner (B01) |
| W00.S2.T4 | Approve processor terms and processing location before any real script leaves the platform | BLOCKED_EXTERNAL | Reg: none. WQ D; BLOCKERS B10. WA-D14: "None approved, so no real-script call is possible" | A PROCESSOR_APPROVED record for each provider | B10, WA-D14 |
| W00.S3.T1 | Define release evidence before implementation | IMPLEMENTED (record) | Reg `W00.S3.T1-T2`; `RELEASE_CHECKLIST.md` "Written-assessment release levels R0-R3"; WQ A | Owner acceptance of the map | Owner (acceptance only) |
| W00.S3.T2 | Resolve policy defaults with accountable owners | IMPLEMENTED (record; 0 of 15 approved) | Reg `W00.S3.T1-T2`; the `DECISIONS.md` WA-D01 to WA-D15 register gives each decision's interim default and approval state ("None has an owner or lead approval on record") | Owner or lead approval of each WA-D | WA-D01 to WA-D15 (owner) |
| W00.S3.T3 | Establish a dependency-based estimate | TODO | Reg: none. WQ D ("audit: partial"); Audit: partial. DEPENDENCIES wave G "spikes → estimates" is TODO. No written estimate exists in the records | An initial estimate that separates content preparation, implementation, annotation, qualification and staffing (possible now); the final estimate after the spikes | Final estimate: B10, owner staffing |

### W01 — Written question bank, rubrics and evaluation evidence

| ID | Title | Status | Evidence (register row / decision / tests) | Remaining | Blocker |
|---|---|---|---|---|---|
| W01.S1.T1 | Extend the question taxonomy | PARTIAL | Reg `W01.S1.T1` (says IMPLEMENTED); TAXONOMY-01 (#224): numerical and derivation types, with learners offered short and long only; `test_written_taxonomy.py`; W01 stage row (IMPL-19: short and long, subparts, maxima, languages) | Shared passages and assets for written questions; written-question diagram requirements (TAXONOMY-01's consequences; P08.S1.T1 rows). Offering the new types | Passages and diagrams: none (possible now). Offering: WA-D11 |
| W01.S1.T2 | Encode board and custom form rules | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked | Board patterns read by a reviewer; composite child contracts | B02, WA-D15, B01 |
| W01.S1.T3 | Publish only reviewed content | PARTIAL | Reg: none. The W01 stage row applies, and the book-draft rows cite this task only as the review rule. Audit: partial. Publication gate (IMPL-14, IMPL-19); independent review (`test_content_workflow.py`); rights gate (`publication_rights`, P22.S1); incomplete rubrics never enter forms (W04.S1.T1) | An outcome-mapping gate (the books print no SLO codes); academic approval. `content/` holds no written questions or rubrics yet | B01 |
| W01.S2.T1 | Define bounded criteria | IMPLEMENTED | Reg `W01.S2.T1`; IMPL-19, RUBRIC-PATHS-01; `test_written_records.py`; WQ A | Imports of the owner's rubrics | None (content needs B01) |
| W01.S2.T2 | Encode alternative and consequential marking | IMPLEMENTED (mechanism) | Reg `W01.S2.T2`; MARKING-RULES-01 (#221), ACADEMIC-REVIEW-01; `test_marking_rules.py`; Playwright guide-method journey | Rule wording for real marking guides | B01 |
| W01.S2.T3 | Review and version rubrics independently | IMPLEMENTED | Reg `W01.S2.T3`; IMPL-14, IMPL-19, ADJ-01; `test_content_workflow.py`, `test_rubric_adjudication.py`; WQ A | Academic approval of real rubrics | B01 |
| W01.S3.T1 | Build the real-script evaluation inventory | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked | An inventory of consented real scripts | B10 |
| W01.S3.T2 | Produce teacher labels and adjudications | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked. The calibration tooling exists (CALIBRATION-01, W06.S1.T3), but it is not this task's evidence | Two independent teacher marks and an adjudication for each real script | B10, B01 |
| W01.S3.T3 | Freeze development/calibration/held-out splits | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked | Splits on real data; preregistered counts and thresholds | B10, WA-D06 |

### W02 — Domain contracts and technical foundation

| ID | Title | Status | Evidence (register row / decision / tests) | Remaining | Blocker |
|---|---|---|---|---|---|
| W02.S1.T1 | Model immutable evidence and attempts | PARTIAL | Reg: none. Audit: partial. Hashes, logical pages, frozen forms, receipts and rescans (IMPL-20, EVIDENCE-01, RESCAN-01/02); mapping revision history (REGION-MAP-01, #355) | Retention and deletion references across every record | B15, WA-D10 |
| W02.S1.T2 | Model assessment and review provenance | PARTIAL | Reg: none. Audit: partial. Score versions, effective adjudication sets and separate assessor proposals; there is no automatic publication path (AUTOASSESS-01, ADJ-01, PILOT-R0-01) | Joint reading alternatives; an explicit human-protection marker for automatic publication | B10, WG10 |
| W02.S1.T3 | Model allowance and operational state | IMPLEMENTED | Reg `W02.S1.T3`; COMPLETENESS-01, ALLOC-01, ADMIT-01, IMPL-22; `test_question_outcomes.py`, `test_access.py`, `test_permit_admission.py`; WQ A | None | None |
| W02.S2.T1 | Publish client/server schemas | IMPLEMENTED | Reg `W02.S2.T1`; CLIENTS-01, EVIDENCE-01; contract drift check in CI; `test_client_policy.py`, `test_evidence.py` | None | None |
| W02.S2.T2 | Specify receipt and job transactions | IMPLEMENTED | Reg `W02.S2.T2`; IMPL-20, ALLOC-01/02, PUB-01; `test_written_attempts.py`, `test_publication_integrity.py`, `test_evidence.py` | None | None |
| W02.S2.T3 | Specify privacy and academic boundaries | IMPLEMENTED | Reg `W02.S2.T3`; WRITTEN-AUTHZ-01, WRITTEN-INJECTION-01, ADJ-01; `test_written_authz.py`, `test_written_injection.py` | None | None |
| W02.S3.T1 | Run bounded real-script reading spikes | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked | Spikes on accepted real scripts | B10, W00.S2.T4 |
| W02.S3.T2 | Validate storage and worker foundations | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked. The LocalStack emulator run (P03.S1.T2) is development evidence only | Real object storage; one real end-to-end job; rolling overlap | B03, B10 |
| W02.S3.T3 | Record implementation decisions | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked | Choices of adapter, model and queue from spike measurements | B10, WA-D05 |

### W03 — Capture, scanning, mapping and upload

| ID | Title | Status | Evidence (register row / decision / tests) | Remaining | Blocker |
|---|---|---|---|---|---|
| W03.S1.T1 | Implement browser capture/import | IMPLEMENTED (web) | Reg `W03.S1.T1`; IMPL-20; `test_evidence.py`; written E2E (`practice.spec.ts`: upload, and a PDF shown one page per PDF page); WQ A | Memory limits on reference browsers and devices; the large-PDF page-by-page preview (the register's remaining item) | B09, B14 |
| W03.S1.T2 | Implement native capture/import | PARTIAL (code only) | Reg `W03.S1.T2`; CAPTURE-01, OCT14-01, OCT14-04, NATIVE-W01; mobile host tests in `apps/mobile/tests`, typecheck, lint | Verification on qualified Android and iOS devices | B14 (B07, B09, B13) |
| W03.S1.T3 | Implement conservative transformations | PARTIAL (web; mobile code) | Reg `W03.S1.T3 Conservative transformations`; TRANSFORMS-01, MOBILE-TRANSFORMS-01/02, STRAIGHTEN-01 (rollout at 0%); `test_page_transforms.py`; Playwright journey | Qualification on real faint-ink and pencil scripts; mobile on a device | B10, B14 |
| W03.S1.T4 | Implement progressive upload and the capture resolution policy | PARTIAL | Reg: none. Audit: partial. Uploads are open from the start of the attempt; `capture_policy_version` is pinned per form (`modules/written/models.py`); the WA-D13 interim default says "no measured preset" | A measured resolution preset and a higher-detail fallback, qualified on reference phones; byte distributions | WA-D13, B09, B14 |
| W03.S2.T1 | Add actionable quality checks | IMPLEMENTED (provisional thresholds) | Reg `W03.S2.T1`; SCAN-QUALITY-01; `test_scan_quality.py`, `test_evidence.py`; WQ A | Threshold calibration on real scans; device check | B10, B14 |
| W03.S2.T2 | Build page and question mapping | IMPLEMENTED (API + web; mobile confirms numbering only) | Reg `W03.S2.T2/T3` (stale: says PARTIAL). REGION-MAP-01 (#355, merged 2026-10-21; api, web and mobile CI green): areas stored in the original page's coordinates, mapping revision history (migration `20261021_3b7e2a9c4d51`, `GET .../manifest/revisions`), explicit page order, shared-page numbering confirmed before sealing. Tests: `test_region_mapping.py` (6), `e2e/written-areas.spec.ts`, updated written journeys | Area marking on mobile (mobile keeps areas marked on the web and confirms numbering); device check; ambiguity detected by a reader | B14; B10 |
| W03.S2.T3 | Check completeness and duplicates | IMPLEMENTED | Reg `W03.S2.T2/T3` (stale: says PARTIAL). NEAR-DUP-01 (#200); exact deduplication within an attempt (`uq_written_file_attempt_hash`); completeness before sealing; `test_near_duplicate_pages.py`, `test_written_attempts.py`; WQ A | Near-duplicate thresholds on real scans; deletion references (W02.S1.T1) | B10, B15 |
| W03.S3.T1 | Implement private direct uploads | PARTIAL | Reg `W03.S3.T1/T2` (over-claims IMPLEMENTED). EVIDENCE-01: uploads go through the API, bound to account and attempt, with the hash checked; evidence writes are exclusive, so nothing is overwritten (P03.S1.T2 emulator run); `test_evidence.py`. `apps/api` has no presigned or upload-session code. WQ D agrees | Short-lived, signed direct-to-store upload sessions bound to the attempt | Production store B03 (can be built now against the LocalStack emulator) |
| W03.S3.T2 | Implement bounded file validation | IMPLEMENTED | Reg `W03.S3.T1/T2`; EVIDENCE-01, UPLOAD-SCAN-01; `test_evidence.py`, `test_upload_scanning.py`, `test_written_injection.py`; WQ A | Linux memory caps verified in deployment | B03 |
| W03.S3.T3 | Verify interruption and concurrency recovery | IMPLEMENTED (web; native pending) | Reg `W03.S3.T3`; INTERRUPTIONS-01, UPLOAD-RETRY-01; `e2e/written-interruptions.spec.ts`, `test_written_attempts.py`; WQ A | A native app restart on a device; the "expired upload URL" case waits for signed sessions (W03.S3.T1) | B09, B14 |

### W04 — Written forms, timed practice and submission

| ID | Title | Status | Evidence (register row / decision / tests) | Remaining | Blocker |
|---|---|---|---|---|---|
| W04.S1.T1 | Implement the written-test builder | IMPLEMENTED | Reg `W04.S1.T1–T3`; QUESTION-TYPES-01 (#212); `test_written_question_types.py` | None for this task | None |
| W04.S1.T2 | Freeze form and choice rules | PARTIAL | Reg `W04.S1.T1–T3` (T2 PARTIAL); REGISTER-AUDIT-02; `decision-briefs/choice-sections.md` | Section-choice rules; counted versus extra answers | WA-D03, WA-D15 |
| W04.S1.T3 | Present binding start terms | IMPLEMENTED | Reg `W04.S1.T1–T3`; builder terms; `test_permit_admission.py`, `test_written_pilot.py`, `test_review_staffing.py`; WQ A | The maximum weighted choice reservation (after W04.S1.T2); measured transfer guidance | WA-D03; B09, B14 |
| W04.S1.T4 | Define mixed board-paper parent and child contracts for R3 | BLOCKED_EXTERNAL | Reg: none. Audit: not started; `RELEASE_CHECKLIST.md` R3 "Not started" | CompositeBoardForm and CompositeBoardAttempt | WA-D15, B02 |
| W04.S2.T1 | Separate writing and upload time | IMPLEMENTED | Reg `W04.S2.T1–T3`; WRITTEN-CONNECTION-01 (#199); Playwright `written-interruptions.spec.ts` | None | None |
| W04.S2.T2 | Implement the seal transaction | IMPLEMENTED | Reg `W04.S2.T1–T3`; IMPL-20, DBHOLD-01; `test_written_attempts.py`, `test_evidence.py`, `test_empty_seal.py`, `test_connection_holds.py` | Parent-child identity (R3) | WA-D15 (R3 only) |
| W04.S2.T3 | Verify races and retries | IMPLEMENTED | Reg `W04.S2.T1–T3`; CUTOFF-RACES-01 (#211); `test_written_cutoff_races.py` | None | None |
| W04.S3.T1 | Resolve unsubmitted/expired drafts | IMPLEMENTED | Reg `W04.S3.T1`; `test_written_attempts.py::test_nothing_is_admitted_after_the_upload_cutoff`; WQ A | Untimed recovery, where policy permits | Owner policy |
| W04.S3.T2 | Implement authorised readability rescans | IMPLEMENTED (web; teacher route) | Reg `W04.S3.T2 / W06.S2.T4`; RESCAN-01, RESCAN-02, REVIEW-PR32; `test_rescans.py`, `test_rescan_corrections.py`, `test_pr32_corrections.py`; E2E | Mobile rescans on a device | B14 |
| W04.S3.T3 | Separate new learning attempts | IMPLEMENTED (web; mobile code) | Reg `W04.S3.T3`; LINKED-01, MOBILE-LINKED-01 (#207); `test_linked_attempts.py`, `apps/mobile/tests/linked-practice.test.ts` | Device check | B14 |

### W05 — Reading and rubric-based assessment

| ID | Title | Status | Evidence (register row / decision / tests) | Remaining | Blocker |
|---|---|---|---|---|---|
| W05.S1.T1 | Implement the qualified reading adapter | BLOCKED_EXTERNAL | Reg: only the `W05` stage row (PARTIAL; remaining "reading adapter (W05.S1)"). `apps/api` has no reading-record code | A reading adapter with regions and alternatives, bound to the evidence hash | B10 |
| W05.S1.T2 | Reconcile mapping and unreadable regions | BLOCKED_EXTERNAL | Reg: `W05` stage row only. WQ D | Detect missing continuations and contradictory readings | B10 |
| W05.S1.T3 | Calibrate escalation signals | BLOCKED_EXTERNAL | Reg: the `W05` stage row names calibration. WQ D. Calibration subsets exist (CALIBRATION-01) but carry no labels | Calibration labels; observable signals | B10, WA-D06 |
| W05.S1.T4 | Implement the alternative-invariance and blank-evidence rules | PARTIAL | Reg: `W05` stage row only. The blank-evidence half exists: the AUTOASSESS-01 contract sends `blank` and `unreadable` flags to review and never infers zero (`modules/written/automatic.py`; `test_written_automatic.py::test_invalid_or_uncertain_outputs_never_become_proposals`), and learners confirm an answer as unanswered before sealing (W03.S2.T3) and after it (RESCAN-01) | Invariance across jointly plausible reading variants, through a qualified assessor | B10 |
| W05.S2.T1 | Build constrained assessment prompts/inputs | IMPLEMENTED (contract level) | Reg `W05.S2.T1`; AUTOASSESS-01; `test_written_automatic.py` | A real provider prompt | B10 |
| W05.S2.T2 | Validate all academic arithmetic | IMPLEMENTED | Reg `W05.S2.T2`; `test_written_automatic.py`, `test_written_marking.py` | None | None |
| W05.S2.T3 | Route unsupported reasoning safely | IMPLEMENTED (teacher marking) | Reg `W05.S2.T3`; ACADEMIC-REVIEW-01; `test_academic_review.py`; `written-results.spec.ts` | Automatic detection | B10 |
| W05.S3.T1 | Add retries and reconciliation | IMPLEMENTED (fixture assessor) | Reg `W05.S3.T1`; AUTOASSESS-01, AUTO-RECOVERY-01; `test_written_automatic.py`, `test_written_auto_recovery.py` | Idempotency on the provider's side | B10 |
| W05.S3.T2 | Fence publication and record provenance | IMPLEMENTED (fixture; no automatic publication path) | Reg `W05.S3.T2-T3`; AUTO-PROVENANCE-01; `test_written_auto_provenance.py` | The fenced automatic writer after WG10; cost from provider prices | B10, WG10 |
| W05.S3.T3 | Verify controlled failure behaviour | IMPLEMENTED (fixture) | Reg `W05.S3.T2-T3`; `test_written_automatic.py`, `test_written_auto_provenance.py` | Real provider failure modes | B10 |

### W06 — Teacher review, rechecks and academic corrections

| ID | Title | Status | Evidence (register row / decision / tests) | Remaining | Blocker |
|---|---|---|---|---|---|
| W06.S1.T1 | Display complete evidence and rubric context | IMPLEMENTED | Reg `W06.S1.T1` and `W06.S1.T1a`; IMPL-21, DETAIL-01; the marking workspace shows learner-marked areas (REGION-MAP-01); `test_written_marking.py`, `test_detail_view.py`; E2E | Reading alternatives | B10 |
| W06.S1.T2 | Implement safe assignment and decisions | IMPLEMENTED | Reg `W06.S1.T2`; CASE-HANDBACK-01 (#198); `test_written_marking.py`, `test_case_handback.py`; `written-results.spec.ts` | Assigning to a named teacher is not offered (a design choice) | None |
| W06.S1.T3 | Support independent calibration | IMPLEMENTED (engineering) | Reg `W06.S1.T3`; CALIBRATION-01, E2E-GAPS-01 (#213); `test_calibration.py`; staff axe audit | The verdict journey with real proposals | B10 |
| W06.S2.T1 | Add a clear recheck request flow | IMPLEMENTED | Reg `W06.S2.T1`; RECHECK-01; `test_recheck.py`; `written-results.spec.ts` | Email and push notices | B04, B07 |
| W06.S2.T2 | Implement authorised score corrections | IMPLEMENTED (in-app notices) | Reg `W06.S2.T2` (stale: says PARTIAL); RECHECK-01, PUB-01, ADJ-01, NOTIF-01 (`written.result_released` per score version, `score.revised` per adjudication); `test_recheck.py`, `test_publication_integrity.py`, `test_rubric_adjudication.py` (one notice per learner); WQ A | Email and push delivery (P15.S1.T2) | B04, B07 |
| W06.S2.T3 | Process rubric adjudications across attempts | IMPLEMENTED | Reg `W06.S2.T3`; ADJ-01, REVIEW-W06, REVIEW-PR36; `test_rubric_adjudication.py`, `test_w06_review.py`, `test_pr36_review.py`; `adjudication.spec.ts` | Load evidence at production scale; automatic regrades | B03, B10 |
| W06.S2.T4 | Classify readability, new-content and indeterminate rescans | IMPLEMENTED | Reg `W04.S3.T2 / W06.S2.T4`; RESCAN-01/02, REVIEW-PR32; `test_rescans.py`, `test_pr32_corrections.py`; E2E clearer-copy journey | Device check | B14 |
| W06.S3.T1 | Forecast and monitor review demand | PARTIAL | Reg `W06.S3.T1`; STAFFING-01, QUEUE-AGEING-01, DEMAND-01, MARKING-TIME-01; `test_question_outcomes.py`, `test_review_demand.py`, `test_queue_ageing.py` | Recheck demand counted in admission; escalation and audit terms; actual active review minutes | WA-D08, B10. Active minutes: none (possible now) |
| W06.S3.T2 | Define overload and incident responses | IMPLEMENTED (engineering) | Reg `W06.S3.T2`; STAFFING-01, E2E-GAPS-01, STAFFING-E2E-ORDER-01; `test_review_staffing.py`; `service-overview.spec.ts` | Real staffing figures | B01 |
| W06.S3.T3 | Train and qualify reviewers | PARTIAL | Reg `W06.S3.T3`; CALIBRATION-01, REVIEWER-QUALITY-01; `test_reviewer_quality.py` | Approved examples; discrepancy discussion; periodic calibration rounds | B01, WA-D08 |

### W07 — Results, feedback and learning experience

| ID | Title | Status | Evidence (register row / decision / tests) | Remaining | Blocker |
|---|---|---|---|---|---|
| W07.S1.T1 | Build marks and status presentation | IMPLEMENTED | Reg `W07.S1.T1` and `W07 Completeness`; RESULT-ARITHMETIC-01 (#196), COMPLETENESS-01; `test_question_outcomes.py`; `practice.spec.ts` | Exports and notifications don't yet carry P and U; mobile device check | B14 |
| W07.S1.T2 | Link feedback to scan evidence | IMPLEMENTED (sealed pages and clearer copies) | Reg `W07.S1.T2`; FEEDBACK-EVIDENCE-01, FEEDBACK-COPIES-01 (#218); `test_feedback_evidence.py`, `test_feedback_on_copies.py` | Free-drawn regions; device check | B14 |
| W07.S1.T3 | Respect answer-release policies | IMPLEMENTED (mechanism) | Reg `W07.S1.T3`; OCT9-01, MODEL-ANSWER-01; `test_model_answers.py` | Reviewed worked answers | B01 |
| W07.S1.T4 | Publish compatible composite board-paper results for R3 | BLOCKED_EXTERNAL | Reg: none. Audit: not started; `RELEASE_CHECKLIST.md` R3 | Composite parent results | WA-D15, B02 |
| W07.S2.T1 | Provide targeted next steps | IMPLEMENTED | Reg `W07.S2.T1`; NEXT-STEPS-01; `test_next_steps.py`, `test_review_lesson_links.py` | Real misconceptions, with reviewed content | B01 |
| W07.S2.T2 | Add score and attempt history | IMPLEMENTED | Reg `W07.S2.T2`; HISTORY-01; `test_written_history.py`, `test_rubric_adjudication.py`; `written-results.spec.ts` | Device check | B14 |
| W07.S2.T3 | Isolate written learning signals | IMPLEMENTED | Reg `W07.S2.T3`; WRITTEN-SIGNALS-01, COMPARISON-01; `test_written_signals.py` | None | None |
| W07.S3.T1 | Test reading and navigation | IMPLEMENTED (web) | Reg `W07.S3.T1`; WRITTEN-A11Y-01; `e2e/written-reading.spec.ts` (desktop) | Equations (renderer, P01.S4.T2); a manual screen-reader review; learner scan zoom in the phone projects | P19.S2.T3 (a person); B14 |
| W07.S3.T2 | Test interrupted processing journeys | IMPLEMENTED (web and API) | Reg `W07.S3.T2`; INTERRUPTIONS-01; `test_written_interruptions.py`; `written-receipts.spec.ts` | A native restart on a device | B09, B14 |
| W07.S3.T3 | Validate explanation language | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked | Terminology checks by subject reviewers; Urdu and Roman Urdu feedback | B01 |

### W08 — Allowances, privacy and security

| ID | Title | Status | Evidence (register row / decision / tests) | Remaining | Blocker |
|---|---|---|---|---|---|
| W08.S1.T1 | Configure transparent assessment plans | PARTIAL (provisional) | Reg `W08.S1.T1`; IMPL-22, PILOT-R0-01; `test_written_pilot.py` | Cost-backed weights | WA-D07, B06, B10 |
| W08.S1.T2 | Implement atomic allowance transitions | IMPLEMENTED | Reg `W08.S1.T2`; ALLOC-01, ADMIT-01; `test_access.py`, `test_permit_admission.py`, `test_question_outcomes.py`, `test_empty_seal.py` | Finite remedy deadlines; escalation automation | None |
| W08.S1.T3 | Qualify expiry and revocation cases | IMPLEMENTED (provisional fraud policy) | Reg `W08.S1.T3`; PERMITS-01, E2E-GAPS-01; `test_permits.py`; `written-interruptions.spec.ts` | Fraud policy; refunds | Owner; B06 |
| W08.S2.T1 | Verify end-to-end authorisation | IMPLEMENTED | Reg `W08.S2.T1`; WRITTEN-AUTHZ-01; `test_written_authz.py` (it sweeps every `/v1/written-attempts/` route, so #355's `manifest/revisions` is included); `test_authorization_matrix.py` | Signed URLs, once they exist (W03.S3.T1) | None |
| W08.S2.T2 | Test malicious inputs and model boundaries | IMPLEMENTED (files, awards, contracts) | Reg `W08.S2.T2`; WRITTEN-INJECTION-01; `test_written_injection.py`, `test_evidence.py` | Evaluation of a real model's resistance to prompt injection | B10 |
| W08.S2.T3 | Verify processor and consent controls | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked | Check the approved W00.S2.T4 record against the deployed configuration | B10, WA-D14 |
| W08.S3.T1 | Apply versioned retention policies | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked. WA-D10 interim default: nothing is erased automatically (PRIVACY-01) | Approved periods; a scheduler; scan-expiry display | B15, WA-D10 |
| W08.S3.T2 | Delete across processing systems | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked | Tombstones and deletion across stores and jobs | B15 |
| W08.S3.T3 | Verify restore and incident handling | BLOCKED_EXTERNAL | Reg: none. WQ D; Audit: blocked | Tombstone replay after a restore; an access-incident exercise | B15, B03 |

### W09 — Performance, resilience, cost and operational readiness

| ID | Title | Status | Evidence (register row / decision / tests) | Remaining | Blocker |
|---|---|---|---|---|---|
| W09.S1.T1 | Trace the full script lifecycle | IMPLEMENTED (operators; this deployment's own traffic) | Reg `W09.S1.T1`; LIFECYCLE-01 (#206); `test_written_lifecycle.py`; `service-overview.spec.ts` | Real traffic samples; the reading and assessment stages | B03, B10 |
| W09.S1.T2 | Measure workload and cost distributions | BLOCKED_EXTERNAL | Reg: none. WQ D. The ECONOMICS-01 calculator and the LIFECYCLE-01 timings exist, but there is no real traffic or provider pricing | Real samples, provider prices, plan margin | B03, B10, B06 |
| W09.S1.T3 | Configure bounded resources | PARTIAL | Reg `W09.S1.T3`; WORKLOAD-GUARD-01 (#220), POOL-CAPS-01; `test_workload_guard.py`, `test_pool_caps.py`; `CAPACITY_BUDGET.md` | Measured thresholds; CPU and memory limits; provider concurrency | B03, B10 |
| W09.S2.T1 | Run the mixed 5,000-user workload | BLOCKED_EXTERNAL | Reg: none. WQ D. The LOAD-01 generator covers the practice journey only | A load run on real infrastructure | B03 |
| W09.S2.T2 | Run sustained and burst script arrivals | BLOCKED_EXTERNAL | Reg: none. WQ D | Burst runs | B03 |
| W09.S2.T3 | Exercise constrained clients and networks | BLOCKED_EXTERNAL | Reg: none. WQ D | Low-memory phones; weak links | B09, B14 |
| W09.S3.T1 | Run failure and restore exercises | BLOCKED_EXTERNAL | Reg: none. WQ D. The local recovery tests (AUTO-RECOVERY-01) are not restore exercises | Restores of the database and object store; deployment restarts | B03 |
| W09.S3.T2 | Staff and rehearse operations | BLOCKED_EXTERNAL | Reg: none. WQ D | A rehearsal with real staff | B01, owner |
| W09.S3.T3 | Approve cost and capacity limits | BLOCKED_EXTERNAL | Reg: none. WQ D | Measured limits; owner approval | WA-D07, WA-D08, B03, B10 |

### W10 — Academic qualification and staged capability expansion

| ID | Title | Status | Evidence (register row / decision / tests) | Remaining | Blocker |
|---|---|---|---|---|---|
| W10.S1.T1 | Execute R0 on real learner scripts | BLOCKED_EXTERNAL | Reg: none. WQ D. The R0 pilot switch exists (PILOT-R0-01); `RELEASE_CHECKLIST.md` R0 needs real scripts and named teachers | An R0 pilot on real scripts | B10, B01 |
| W10.S1.T2 | Compare teachers, readers and graders | BLOCKED_EXTERNAL | Reg: none. WQ D | Analysis on real data | B10, B01 |
| W10.S1.T3 | Validate operational learning value | BLOCKED_EXTERNAL | Reg: none. WQ D | Findings from the pilot | B10, B01 |
| W10.S2.T1 | Freeze candidate policies before the hold-out run | BLOCKED_EXTERNAL | Reg: none. WQ D | Frozen model, prompt, routing and thresholds | B10, WA-D06 |
| W10.S2.T2 | Apply accuracy, uncertainty and coverage gates | BLOCKED_EXTERNAL | Reg: none. WQ D | Gate results on the hold-out set | B10, WA-D06 |
| W10.S2.T3 | Authorise only passing short-answer slices | BLOCKED_EXTERNAL | Reg: none. WQ D. A qualification-record mechanism exists (QUALIFICATION-01, #358), but there are no records | Qualification records | B10, WA-D06 |
| W10.S2.T4 | Verify sample feasibility and per-slice minimums before the hold-out run | BLOCKED_EXTERNAL | Reg: none. WQ D | A preregistered feasibility record | B10, WA-D06 |
| W10.S3.T1 | Qualify required long-answer scopes for R2 | BLOCKED_EXTERNAL | Reg: none. WQ D | Long-answer qualification | B10, B01 |
| W10.S3.T2 | Qualify numerical and diagram routes for R3 | BLOCKED_EXTERNAL | Reg: none. WQ D | Numerical and diagram qualification | B10, WA-D11 |
| W10.S3.T3 | Qualify larger and official-pattern forms for R3 | BLOCKED_EXTERNAL | Reg: none. WQ D | Qualification of official-pattern forms | B10, B02, WA-D15 |
| W10.S3.T4 | Qualify the complete mixed board-paper journey for R3 | BLOCKED_EXTERNAL | Reg: none. WQ D | Qualification of the composite journey | WA-D15, B02, B10, B14 |

### W11 — Controlled rollout, monitoring and handover

| ID | Title | Status | Evidence (register row / decision / tests) | Remaining | Blocker |
|---|---|---|---|---|---|
| W11.S1.T1 | Audit the complete release manifest | BLOCKED_EXTERNAL | Reg: none. WQ D. The release manifest (RELEASE-01, RELEASE-CANDIDATE-01, `portal_api/release.py`) has no written-capability section | The audit before P21 and P23; a written-capability section in the manifest can be prepared now | WG10/B10, B03 |
| W11.S1.T2 | Verify the cross-platform real-data journey | BLOCKED_EXTERNAL | Reg: none. WQ D | A run with real content on web, Android and iOS | B01, B10, B14 |
| W11.S1.T3 | Publish accurate help and terms | PARTIAL | Reg: none. WQ D says TODO. Six written help drafts from HELP-01 (2026-10-09) exist in `apps/api/help_articles/en/`: `written-allowance`, `-clearer-copy`, `-marking-and-results`, `-recheck`, `-submission-receipt` and `-upload-limits`; `test_help.py` | Check the drafts against the current behaviour; Urdu; retention and recheck limits; terms; publication | B15, WA-D07, owner and legal, B01 (Urdu) |
| W11.S2.T1 | Enable a bounded learner cohort | BLOCKED_EXTERNAL | Reg: none. WQ D. Rollout flags exist (ROLLOUT-01) | A live cohort | B03, WG10 |
| W11.S2.T2 | Audit released marks and upheld rechecks | BLOCKED_EXTERNAL | Reg: none. WQ D | Live sampling audits | B03, B10, WA-D06 |
| W11.S2.T3 | Rehearse rollback and student remediation | BLOCKED_EXTERNAL | Reg: none. WQ D. Feature switches (OPS-01 `new_written_tests`) and the workload guard exist; there is no live automatic route to disable | A rehearsal of disabling a live automatic route | B10, B03 |
| W11.S2.T4 | Run the canary drift monitor | BLOCKED_EXTERNAL | Reg: none. WQ D | A consented canary baseline | B10 |
| W11.S3.T1 | Deliver operator and academic runbooks | PARTIAL | Reg: none. WQ D says TODO. `docs/runbooks/alerts.md` has sections on the regrade backlog, automatic assessment, the marking backlog and the workload guard (OPS-01, WORKLOAD-GUARD-01) | Runbooks for review assignment, rescan classification, rubric corrections, evidence deletion, spend limits, drift holds and academic incidents; named owners; a controlled exercise | W00.S2.T3 (owner), B15, B10 |
| W11.S3.T2 | Establish requalification triggers | PARTIAL | Reg: none. WQ D says TODO. QUALIFICATION-01 (#358, CI green): the `portal_api/qualification.py` trigger `written_pipeline` invalidates written academic, capture, workload-cost and canary records when a rubric, model, prompt, OCR, preprocessing, capture, notation or routing change is made, and `written_state` covers state, allowance and result propagation; `test_qualification.py` asserts both. AUTO-PROVENANCE-01 rejects unexpected model versions. There is no automatic publication path that a fallback could use | Written qualification records for the triggers to invalidate (none exist; W10); a DECISIONS row for QUALIFICATION-01 | B10 |
| W11.S3.T3 | Maintain module/master continuity | IN_PROGRESS | This file. WQ C still says TODO | Link this file from the register; apply the corrections below; keep this file current with every W change | None |

## Stale register rows

Each row names the record and its row label, says what the record shows, gives the evidence on `main` and recommends a
correction. None of these corrections has been applied: this file edits no other record.

### IMPLEMENTATION_REGISTER.md

| # | Row | Record says | Evidence | Recommended correction |
|---|---|---|---|---|
| 1 | `W03.S2.T2/T3 Mapping and completeness` | PARTIAL. Remaining: "region-level mapping in canonical coordinates, a mapping revision history, explicit reorder, numbering confirmation" | #355 was merged on 2026-10-21 with api, web and mobile CI green. It covers REGION-MAP-01, migration `20261021_3b7e2a9c4d51`, `test_region_mapping.py` (6) and `e2e/written-areas.spec.ts` | Split the row. W03.S2.T2 becomes IMPLEMENTED (API + web; mobile confirms shared-page numbering and keeps areas marked on the web; device check B14; reader-detected ambiguity B10). W03.S2.T3 becomes IMPLEMENTED (NEAR-DUP-01; thresholds B10) |
| 2 | `W01.S1.T1 Extend the question taxonomy` | IMPLEMENTED (authoring and review) | TAXONOMY-01's own consequences list "shared passages for written questions" as remaining. The P08.S1.T1 rows list "written-question passages and diagrams" as remaining. Roadmap subpoint 2 requires shared passages and assets | Change to PARTIAL. Missing: shared passages and assets and diagram requirements for written questions (possible now); offering the new types needs WA-D11 |
| 3 | `W03.S3.T1/T2 Private uploads and validation` | IMPLEMENTED (dev store) for both | `apps/api` has no signed or presigned upload-session code; uploads go through the API. WQ D row `W03.S3.T1` says the same. The roadmap's T1 requires "signed authorisation" | Split the row. W03.S3.T1 becomes PARTIAL (no direct signed upload sessions; production store B03; can be built against LocalStack now). W03.S3.T2 stays IMPLEMENTED |
| 4 | `W06.S2.T2 Authorised score corrections` | PARTIAL. The only remaining item: "email and push wait on B04 and B07" | In-app notices: `written.result_released` per score version (`review.py`) and `score.revised` per adjudication (`adjudication.py`); `test_rubric_adjudication.py` asserts one notice. WQ A lists the task as implemented | Change to IMPLEMENTED (in-app notices). Email and push are P15.S1.T2 channels (B04, B07) |
| 5 | `W00.S1.T1 Freeze the student outcomes and exclusions` | "RECORDED", which is not one of the register's states | `LAUNCH_MANIFEST.md` section marked PROPOSED; WA-D12 "Not recorded" | Change to PARTIAL (proposal recorded; the freeze waits on WA-D12) |
| 6 | `W08.S2.T1 Verify end-to-end authorisation` | "region ownership and signed URLs not applicable yet" | Regions have existed since REGION-MAP-01. `update_manifest` refuses an area on a page the slot doesn't use (`test_region_mapping.py`). `test_written_authz.py` sweeps every `/v1/written-attempts/` route, including the new `manifest/revisions` | Narrow the caveat to "signed URLs not applicable yet (W03.S3.T1)" |
| 7 | `W06.S1.T1 Evidence and rubric context` | Remaining: "Region zoom, reading alternatives" | DETAIL-01 provides region renditions (row `W06.S1.T1a`). The marking workspace draws the learner's areas (`marking-workspace.tsx`, `AreaOverlay`, #355) | Remaining becomes "reading alternatives (B10)" |
| 8 | `W03/W04/W06 native learner journey` | Remaining includes "offline capture queue; native PDF selection" | CAPTURE-01 (row `W03.S1.T2`): pages are kept on the phone until uploaded, and PDFs are imported with the system picker | Remove both items. Keep devices (B07, B08, B13, B14) and automated mobile E2E |
| 9 | `W04.S3.T2 / W06.S2.T4 Readability rescans and classification` | Remaining: "Mobile learner screens; notifications" | NATIVE-W01 provides mobile rescans with idempotency keys and confirm-unanswered. In-app `written.action_required` notices exist (`review.py`, NOTIF-01) | Remaining becomes "device check (B14); email and push (B04, B07)" |
| 10 | `W06.S2.T1 Learner rechecks` | Remaining: "Notices (P15.S1)" | In-app notices have existed since NOTIF-01 | Remaining becomes "email and push (B04, B07)" |
| 11 | `W01 Written question and rubric records` (stage row) | IMPLEMENTED (records + studio) for the whole of W01 | W01.S1.T2 and W01.S3.T1 to T3 are BLOCKED_EXTERNAL. W01.S1.T1 and W01.S1.T3 are PARTIAL | Rescope the row to the records slice (W01.S1.T1 in part, W01.S2.T1 to T3) or mark it superseded by the per-task rows |
| 12 | Nine book-draft rows `P07.S1 / W01.S1 ...` (Class XI and XII Biology, Chemistry, Physics, Computer Science; XI figures) | Tagged W01.S1 | W01.S1 is "Author written questions and patterns", but these rows record lesson drafts. `content/` has no written questions or rubrics | Drop the `W01.S1` tag (they are P07.S1). Keep "academic review before publication (W01.S1.T3)" only in Remaining, so they are never counted as W01.S1 evidence |
| 13 | `W05 Automatic reading and rubric assessment` (stage row) | PARTIAL for all of W05 | W05.S2 and W05.S3 now have their own rows (IMPLEMENTED at fixture or contract level) | Relabel it as the W05.S1 umbrella row, or mark it superseded for W05.S2 and W05.S3 |
| 14 | Header: "Any task not listed is `TODO`" | 57 W IDs have no row of their own | This file: 47 BLOCKED_EXTERNAL, 8 PARTIAL, 1 TODO, 1 IN_PROGRESS | Link this file from the register as the W status source, or add the 57 rows |

### Other records

| # | Record / row | Record says | Evidence | Recommended correction |
|---|---|---|---|---|
| 15 | `DECISIONS.md` | No REGION-MAP-01 row | Cited by the migration `20261021_3b7e2a9c4d51`, `modules/written/{mapping,service,models,evidence,review}.py`, `test_region_mapping.py` and seven e2e specs (#355) | Add the REGION-MAP-01 row: areas in the original page's coordinates, manifest revision history table, explicit page reorder, shared-page numbering confirmed before sealing |
| 16 | `DECISIONS.md` | No QUALIFICATION-01 row | `docs/project/qualification/README.md`, `RELEASE_CHECKLIST.md` and `portal_api/qualification.py` (#358) cite it | Add the row; P20.S4.T4 is the main task, and it is also W11.S3.T2 evidence |
| 17 | `RESUME_STATE.md`, Next actions item 0 | "Still to check against the code before building: container images (P03.S3.T2), page-region mapping (W03.S2.T2)" | Both are merged: #234 and #355 | Mark both as done |
| 18 | `WORK_QUEUE.md` C `W01.S1.T1` | TODO; "Add numerical and derivation types" | TAXONOMY-01 (#224) | PARTIAL; move it out of C, leaving passages and diagrams |
| 19 | `WORK_QUEUE.md` C `W01.S2.T2` | TODO; "Add sig-fig and multiple-final-answer/contradiction rule fields" | MARKING-RULES-01 (#221); `test_marking_rules.py` | IMPLEMENTED (mechanism); move to A with B01 remaining |
| 20 | `WORK_QUEUE.md` C `W03.S2.T2`; execution order #16 | Region mapping still to build | #355 | IMPLEMENTED; move to A |
| 21 | `WORK_QUEUE.md` C `W04.S3.T3`; execution order #3 | "Mobile has no screen to prepare a linked practice test" | MOBILE-LINKED-01 (#207) | Move to A (device check B14) |
| 22 | `WORK_QUEUE.md` C `W07.S1.T2`; execution order #8 | "Anchors on clearer copies" | FEEDBACK-COPIES-01 (#218) | Move to A (device check B14) |
| 23 | `WORK_QUEUE.md` C `W09.S1.T1`; execution order #2 | TODO ("not in register or audit") | Register row `W09.S1.T1`; LIFECYCLE-01 (#206) | IMPLEMENTED; move to A |
| 24 | `WORK_QUEUE.md` C `W09.S1.T3`; execution order #9 | TODO ("not in register or audit") | Register row `W09.S1.T3`; WORKLOAD-GUARD-01 (#220) | PARTIAL; move to D (B03, B10) |
| 25 | `WORK_QUEUE.md` C `W11.S3.T3` | TODO; "W09-W11 absent" | W09.S1.T1 and W09.S1.T3 now have rows; this file | IN_PROGRESS, then done once this file is linked |
| 26 | `WORK_QUEUE.md` B `W04.S1.T1`, `W04.S2.T3`, `W06.S1.T3`, `W06.S3.T2`, `W08.S1.T3` | Named checks missing | QUESTION-TYPES-01 (#212), CUTOFF-RACES-01 (#211), E2E-GAPS-01 (#213); the W06.S1.T3 verdict journey still needs B10 | Move to A |
| 27 | `WORK_QUEUE.md` D `W03.S3.T1` | Register column "IMPLEMENTED (dev store)" while the class is D | See row 3 | Register column: PARTIAL |
| 28 | `WORK_QUEUE.md` D `W05.S1.T4`, `W11.S1.T3`, `W11.S3.T1`, `W11.S3.T2` | TODO | See the evidence for each in the W05 and W11 tables above | PARTIAL; they stay in D for what remains |
| 29 | `ROADMAP_STATUS_AUDIT.md` partial rows W00.S3.T1, W00.S3.T2, W01.S1.T1, W01.S2.T2, W05.S3.T2 | Missing: the R0–R3 map; the WA-D register; numerical and derivation types; sig-fig and contradiction rules; the configuration hash | `RELEASE_CHECKLIST.md` R0–R3 table; `DECISIONS.md` WA-D register; TAXONOMY-01; MARKING-RULES-01; AUTO-PROVENANCE-01 | Add them to the audit's "Checked again" list. The table rows themselves are kept for the record, by the audit's own rule |
