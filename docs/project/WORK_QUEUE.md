# Work queue (every roadmap task)

**16 October 2026 — topic reader (current priority).** Uncommitted on `feat/topic-reader` (base `7d1be98`). Linked tasks: P11.S2.T1, P13.S2.T1, P07.S1.T1, P01.S4.T2, P22. Decision TOPIC-READER-01.

| Slice | Code | Tested | Device |
|---|---|---|---|
| Topic route, private draft preview, chapter list without PDF badges | Written on native and web | API `test_topic_reading.py` passed locally. OpenAPI not regenerated. | Not device-verified. The installed preview binary has no `/topic/[id]` route. |
| Biology XI 1.1 draft | Imported once into `portal_integrations_view_test` as `C11-BIO-CH1-1.1` | Live check: anonymous unavailable; scoped author sees 29 blocks | Not on the phone |

Mapped: Biology XI chapter 1 topic 1.1, PDF 4–8. Drafted: that topic only. Reviewed: none. Published: none. Figures expected: Fig 1.1–1.4. Created: the bacterial-shapes scene only. Still diagrams of the tree, membranes and archaea groups are not archived. The build the owner should install does not exist yet. External wait: an interactive iOS preview build (Apple team `6FV87T5UMF`, registered iPhone `00008130-000169AE2130001C`) and a second-person academic review before publication.

**Night of 2026-10-15:** `main` is `f3d2a83`. Alembic head is `f8a21c6d4e90`. The counts and the C list below are not a current census. Do not rebuild work that is already on main: the evening items (P12.S2.T3, W09.S1.T3, P06.S4.T2, P09.S3.T1, W01.S1.T1, P02.S2.T1, the support read and the staffing-journey order; then at `8949b49`) and, since then, P13.S2.T1 mobile discovery (#227), P05.S1.T3 edition windows (#228), P03.S1.T2 the development object-store adapter (#229) and P04.S2.T2 the emergency-access audit (#230). #231 (do not choose among overlapping current editions) was open when this note was written and is not evidence until it merges. The sentence “nothing buildable remains” in RESUME_STATE is a 12 October historical note.

Built 2026-10-15 from the roadmap's 423 task IDs (306 core `P..`, 117 written `W..`), the register, BLOCKERS, DECISIONS and
the status audit, with the cited code and test files checked to exist. Classes:

- **A, implemented and verified:** code and automated tests on `main`; anything left is an external gate.
- **B, implemented but not verified enough:** a check that can be done locally is missing (named below).
- **C, incomplete and executable now:** needs no account, credential, device, reviewer, real academic content, money or
  owner decision.
- **D, blocked:** the named dependency (a B-number from BLOCKERS, a WA-D decision, or an owner decision).

A task's class here is separate from its register state and its gate state. A C item is re-checked against the code
before work starts, and moves to A only on a merged PR with green CI. This file is the queue. The register keeps the
evidence.

**Counts:** A 197 · B 26 · C 39 · D 161 now (at classification: core A 159, B 18, C 33, D 96; written A 34, B 6, C 12, D 65).

## Done in this pass (2026-10-15)

| Task | PR | Record |
|---|---|---|
| W07.S1.T1 | #196 | RESULT-ARITHMETIC-01 |
| §6.1 / P10.S2 / P13.S2.T2 | #197 | ANSWER-STATES-01 (and a web network-failure defect) |
| W06.S1.T2 | #198 | CASE-HANDBACK-01 |
| W04.S2.T1 | #199 | WRITTEN-CONNECTION-01 (and the same defect in the written runner) |
| W03.S2.T3 | #200 | NEAR-DUP-01 |
| P15.S3.T1 | #201 | MOBILE-SCREENSHOTS-01 |
| P06.S1.T2 | #202 (open) | ASSIGN-REVIEWER-01 |
| P12.S3.T1 | #203 (open) | NOTEBOOK-FLAGS-01 |

## Flaky or environment-only results (open)

- `e2e/support.spec.ts` "a learner asks for help, staff reply…" failed once in CI (run 38659513933, PR #198): after a reload
  the learner's page didn't show the staff reply within 20 s; it passed on retry. 1 failure in the last 10 web runs. Locally 8 of 8
  passed once and 6 of 8 another time, with a different symptom (`page.reload` timing out on the development server). Cause
  **not established**; the reply path has no cache (`no-store`). Next step: keep the CI trace of the next failure (html report).
- Locally only: `studio.spec.ts` rights gate (dev database has confirmed C11-BIO rights) and `adjudication.spec.ts` (a fixture rubric
  corrected by earlier local runs), as RESUME_STATE says; CI starts from a fresh database.

## Execution order for C (code first, then records)

Smallest learner- or safety-relevant items first; each one lands as its own PR, and its tests are added to the B list's checks where they overlap.

| # | Task | Size | Work |
|---|---|---|---|
| 1 | P17.S2.T2 | M | per-class pool caps, job caps, mock-window pause |
| 2 | W09.S1.T1 | M | per-script lifecycle trace |
| 3 | W04.S3.T3 | M | mobile linked practice |
| 4 | P13.S1.T4 | S/M | publication gate reads oldest registered build |
| 5 | P03.S4.T2 | S/M | correlation IDs into jobs |
| 6 | P01.S1.T2 | S/M | module boundaries + import-graph test |
| 7 | W01.S1.T1 | M | numerical/derivation types |
| 8 | W07.S1.T2 | M | feedback anchors on clearer copies |
| 9 | W09.S1.T3 | M | written work pauses on core health |
| 10 | P08.S3.T1 | M | duplicate stem detection |
| 11 | P06.S4.T2 | S/M | export schema v2 |
| 12 | P09.S3.T3 | M | fixed form per scheduled session |
| 13 | P09.S3.T1 | M | difficulty/outcome allocation |
| 14 | P13.S2.T1 | M | mobile discovery — on main (#227); do not rebuild |
| 15 | W01.S2.T2 | S | rubric sig-fig and contradiction fields |
| 16 | W03.S2.T2 | L | region mapping and mapping history |
| 17 | P05.S1.T3 | M | edition effective dates — on main (#228); do not rebuild |
| 18 | P06.S3.T2 | L | atomic multi-item release |
| 19 | P12.S2.T3 | L | cohort comparisons (after P09.S3.T3) |
| 20 | P03.S1.T2 | M | S3-compatible emulator + adapter — on main (#229); do not rebuild |
| 21 | P03.S3.T2 | M/L | Dockerfiles + CI image digests |
| 22 | P01.S4.T2 | M/L | web equation/notation renderer spike |
| 23 | P02.S2.T1 | S | Urdu font + shared tokens |
| 24 | P20.S4.T4 | M | qualification records + retest trigger tool |
| 25 | P11.S2.T1 | M | focused lesson page (confirm intent first) |

Records-only C items (size S, after the code items, in one records PR): P00.S1.T1, P00.S1.T3, P00.S1.T4, P00.S2.T3,
P00.S3.T2, P01.S2.T2, P01.S3.T1, P02.S1.T3, P02.S2.T2, P03.S1.T3, W11.S3.T3. P04.S2.T2 landed in #230 and is not still a records-only item.

## C: incomplete and executable now (39)

| Task | Title | Register | Remaining | Dependency |
|---|---|---|---|---|
| P00.S1.T1 | Register the owner requirements | IN_PROGRESS | Requirement -> phase -> acceptance-scenario trace table separating requirements, enhancements and Section 17 decisions | none (records roadmap + decisions) |
| P00.S1.T3 | Define initial learners and journeys | not registered (TODO by rule) | Record learner types (XI, XII, repeat, ICS-to-ECAT, purchaser) and first-visit..support journeys linked to specs | none |
| P00.S1.T4 | Record the positioning hypothesis and bounded validation plan | not registered (TODO by rule) | Record hypothesis, competitor claims as vendor claims, bounded interview plan | running interviews needs owner + learners |
| P00.S2.T3 | Define product operating assumptions | not registered (TODO by rule) | Record age range, launch courses, languages, free/paid model, support hours as proposed settings | none to record; owner confirms later |
| P00.S3.T2 | Establish issue severity and acceptance rules | not registered (TODO by rule) | Define P0/P1/lower severities with owners and AC60 gate rules; extend readiness test | none |
| P01.S1.T2 | Define module boundaries | IN_PROGRESS | Document modules and permitted calls; add AST import-graph test | none |
| P01.S2.T2 | Design schema changes and indexes | not registered (TODO by rule) | Schema/index policy: partition thresholds (VOLUME-01 indicative), schema changes that trigger requalification | none |
| P01.S3.T1 | Publish the API contract | IMPLEMENTED (catalogue slice) | API conventions doc: /v1 versioning and deprecation, pagination, errors, auth expectations | none |
| P01.S4.T2 | Prove scientific content rendering | TODO (tracked in LESSON-BLOCKS-01 note) | Renderer v2 spike: typeset equations, chemistry notation, mixed Urdu/English, long options; payload sizes | native half needs B13/B07 |
| P02.S1.T3 | Map every screen state | not registered (TODO by rule) | State map per route (loading, empty, expired, offline, conflict, update-required, score revised, 5 answer states) and gap list | none |
| P02.S2.T1 | Define tokens and typography | not registered (TODO by rule) | Choose/record Urdu font and a token table used by web and mobile | phone readability check B09; brand B11 not blocking |
| P02.S2.T2 | Build component specifications | not registered (TODO by rule) | Component specs: forms, tables, meters, answer-state options, keyboard and disabled states | none |
| P03.S1.T2 | Create reproducible local services | IMPLEMENTED on main (#229); emulator exercised 2026-10-15 | LocalStack 4.7.0. CI used an in-process stand-in. A later local run covered put, get, list, delete, exclusive evidence and prefix isolation, and the admin label was "Development stand-in". | Production bucket and region (B03). Not production qualification. |
| P03.S1.T3 | Establish coding and review conventions | IN_PROGRESS | CONTRIBUTING: startup, seed/reset, debugging, migration naming, commit style; refresh README | none |
| P03.S3.T2 | Build immutable artifacts and variant builds | not registered (TODO by rule) | Dockerfiles (API/workers, web); CI build per commit recording digest in release manifest | registry promotion B03; native variants B07/B13 |
| P03.S4.T2 | Add baseline observability | IMPLEMENTED (API + web) | Carry correlation ID into import/export/notification/regrade/auto-assess job rows and worker logs | none |
| P04.S2.T2 | Protect staff accounts | IMPLEMENTED on main (#230) | `docs/runbooks/emergency-access.md`; `portal-grant-role` writes an audit row with no actor | Not a current C item |
| P05.S1.T3 | Add edition and year boundaries | IMPLEMENTED on main (#228), migration `f8a21c6d4e90` | The grade/subject book endpoint returns 409 when two editions are effective today and does not choose one. A book id still loads. | Real edition dates are an owner decision. Catalogue and discovery still listed both editions until #231. |
| P06.S1.T2 | Build the editorial work queue | IMPLEMENTED | In PR #202 ASSIGN-REVIEWER-01 (publisher assigns from eligible reviewers) | none |
| P06.S3.T2 | Publish versioned content releases | IN_PROGRESS | Atomic multi-item catalogue release with release-level rollback; CDN invalidation later | none (CDN B03) |
| P06.S4.T2 | Provide portable content export | IMPLEMENTED | Add concept/inclusion mappings and asset-version references (schema v2); update docs/content-import.md | none |
| P08.S3.T1 | Add duplicate and canonical family detection | IN_PROGRESS | Exact and near-duplicate stem detection across the bank (pg_trgm), flagged for review | none |
| P09.S3.T1 | Implement constrained selection | SUPERSEDED -> PARTIAL (mocks row) | Allocate by difficulty and outcome with deterministic rounding in forms and mocks | none (official mixes B02 later) |
| P09.S3.T3 | Freeze generated forms and policies | IMPLEMENTED | Fixed comparable form per scheduled session, distinct from varied practice | none |
| P11.S2.T1 | Build the lesson page | PARTIAL | Dedicated focused one-lesson page (row: not built) | player/transcript B05 |
| P12.S2.T3 | Make learner comparisons honest | not registered (TODO by rule) | Cohort snapshot: >=200 distinct learners, earliest attempt, 90 days, midrank ties, hidden below threshold; tests with technical accounts | none (display needs real learners) |
| P12.S3.T1 | Build the mistake notebook | IMPLEMENTED | In PR #203 NOTEBOOK-FLAGS-01 (flagged answers collected and reviewed) | none |
| P13.S1.T4 | Implement client capability and supported-version policy | IMPLEMENTED (server)/code only | Validate publication against the oldest supported build registered manifest (CLIENTS-01 Not done) | pipeline registration B03; D08 B09 |
| P13.S2.T1 | Implement learning screens | PARTIAL; discovery on main (#227) | The Learn tab reads `/v1/discovery`. Host tests are not device evidence. | Rotation and background; lecture player and transcripts (B05); devices (B09, B13) |
| P17.S2.T2 | Separate worker priorities | not registered (TODO by rule) | Per-class pool caps at worker start, job duration caps, bulk workers pause in published mock windows | separate deployments/CPU/memory B03 |
| P20.S4.T4 | Bind qualification evidence to the release manifest | not registered (TODO by rule) | QualificationRecord schema, §6.4 trigger table as release-checklist tool, AC51 demo (payload vs caption change) | none (real records need P20 runs) |
| W01.S1.T1 | Extend the question taxonomy | TODO (W01 stage row IMPLEMENTED; audit: partial) | Add numerical and derivation types with required fields; shared passages/assets for written items; tests | None to build; offering them to learners needs WA-D11 |
| W01.S2.T2 | Encode alternative and consequential marking | TODO (W01 stage row; audit: partial) | Add sig-fig and multiple-final-answer/contradiction rule fields with 20.6.3 proposed defaults; show in marking workspace; tests | None to build; rule content per rubric needs B01 |
| W03.S2.T2 | Build page and question mapping | IMPLEMENTED (row W03.S2.T2/T3) | Region-level mapping in canonical coords; mapping revision history; explicit reorder; numbering confirmation | None (reader-detected ambiguity later needs B10) |
| W04.S3.T3 | Separate new learning attempts | IMPLEMENTED (web) | Mobile has no screen to prepare a linked practice test | None to build; device check B14 |
| W07.S1.T2 | Link feedback to scan evidence | IMPLEMENTED (sealed pages) | Anchors on clearer copies (rescan revisions) with transforms | None (device check B14) |
| W09.S1.T1 | Trace the full script lifecycle | TODO (not in register or audit) | Per-script lifecycle timings (upload during/after writing, seal, queue, review, release) with separate denominators; endpoint and test | None (real-traffic numbers later B03) |
| W09.S1.T3 | Configure bounded resources | TODO (not in register or audit) | Health-coupled pause of written regrade/assessment with hysteresis; reserved ingest/receipt capacity; provisional thresholds | None to build; measured thresholds B03 |
| W11.S3.T3 | Maintain module/master continuity | TODO (not in register or audit) | Register rows for all 117 W IDs (W09-W11 absent); fix stale rows | None |

## B: implemented, verification missing (26)

| Task | Title | Register | Remaining | Dependency |
|---|---|---|---|---|
| P02.S4.T2 | Test assistive interaction | not registered (TODO by rule) | No axe/keyboard checks on exam room+result, mocks, notebook, evidence, plan, progress, studio item editor, /admin pages | manual screen-reader review needs a person |
| P07.S1.T2 | Add multilingual lesson variants | IMPLEMENTED | No e2e for language switch and missing-language fallback | - |
| P09.S1.T2 | Build book and combined scopes | IMPLEMENTED | No e2e for half/full/combined scopes in the web builder | - |
| P09.S1.T3 | Build multi-subject custom practice | IMPLEMENTED | No e2e for the multi-subject builder | - |
| P09.S2.T3 | Configure scheduled mocks | IMPLEMENTED | No browser e2e for self-started/scheduled mock, held results, accommodations | reschedule rules: owner policy |
| P10.S4.T2 | Test timing and serialization boundaries | IN_PROGRESS | Tests for lock wait crossing C, timely admission with later commit, flush at D, duplicate tabs, clock change, suspension | - |
| P10.S4.T3 | Prevent inappropriate exam assistance | IMPLEMENTED | Unchanged by #197; browser test of the MOCK_IN_PROGRESS refusal still missing | - |
| P11.S1.T3 | Build course discovery | IMPLEMENTED | No committed e2e for discovery filters and preview exposure (manual only) | exam filter B02 |
| P11.S3.T1 | Connect practice configuration | IMPLEMENTED | Topic narrowing never exercised in a browser (no topic-tagged fixture) | - |
| P11.S3.T3 | Build completion and recovery screens | IMPLEMENTED | Not-counted notice checked ad hoc only; add committed e2e | resume budget B09 |
| P12.S2.T2 | Build the weak-area view | IMPLEMENTED | /practice/evidence only crawled; no e2e with data checking recommendation and evidence count | - |
| P12.S4.T1 | Build a time-budgeted study plan | IMPLEMENTED | No e2e for the plan page (shortfall, replanning) | exam weights B02 |
| P12.S4.T2 | Support learner reports | IMPLEMENTED | Page only in payload budget/crawl; add e2e for report content | - |
| P13.S2.T2 | Implement assessment screens with the shared cutoff contract | PARTIAL | #197 ANSWER-STATES-01: five answer states on mobile (host test). Device budgets need B09 | device budgets B09 |
| P13.S2.T3 | Implement results and revision | PARTIAL | Deep links to retired/locked/missing content untested (host-side or Expo-web test) | devices |
| P13.S3.T1 | Add controlled study packs | IMPLEMENTED (API)/code only | Mobile pack download/checksum logic has no host-side test | devices |
| P13.S3.T2 | Implement offline progress sync | IMPLEMENTED (API)/code only | Mobile sync queue (op IDs, replay) has no host-side test | devices |
| P13.S3.T3 | Manage cached content access | PARTIAL | Mobile expiry/cleanup/sign-out deletion untested host-side | devices |
| P15.S3.T1 | Build support tickets | IMPLEMENTED (web + mobile) | #201 MOBILE-SCREENSHOTS-01: mobile picker built (host tests); device check needs B09/B14 | device check B13 |
| P19.S3.T3 | Verify versioned reports and privacy isolation | PARTIAL | Report reconciliation vs source (scores, adjudications, trial-device auths, duplicate/delayed events) not built | purchases B06; cohorts P12.S2.T3 |
| W04.S1.T1 | Implement the written-test builder | IMPLEMENTED | Missing test that short-only and long-only builds filter the pool and weights (fixture is short-only) | None |
| W04.S2.T3 | Verify races and retries | IMPLEMENTED | Missing tests: admission exactly at U; lock wait straddling U; concurrent seal vs expiry; manual early seal | None |
| W06.S1.T3 | Support independent calibration | IMPLEMENTED (engineering) | No Playwright/axe for /studio/calibration verdict journey (absent from accessibility.spec.ts) | None for the test; real proposals B10 |
| W06.S3.T2 | Define overload and incident responses | IMPLEMENTED (engineering) | No Playwright for staffing form and learner turnaround/marking-full notice (manual check only) | None for the test; real figures B01 |
| W07.S3.T1 | Test reading and navigation | IMPLEMENTED (web) | Learner result/scan zoom on phone projects; equation-bearing question; manual screen-reader review | None for tests; manual review needs a person (P19.S2.T3) |
| W08.S1.T3 | Qualify expiry and revocation cases | IMPLEMENTED | No Playwright for plan-withdrawn notice (manual check only) | None for the test; fraud policy owner, refunds B06 |

## D: blocked (161)

| Task | Title | Register | Remaining | Dependency |
|---|---|---|---|---|
| P00.S2.T2 | Define content responsibility | BLOCKED_EXTERNAL | Named reviewers, academic lead, rights confirmation | B01 |
| P00.S3.T3 | Create delivery estimates after the real-content spike | not registered (TODO by rule) | Estimates after the real-content spike | P22.S1 acceptance (B01), P01.S4 spikes (B13/B07), W02.S3 (B10) |
| P01.S1.T3 | Select deployment and integration adapters | not registered (TODO by rule) | ADRs plus availability/quota/cost validation | B03,B04,B05,B06,B07,B10 (ADR write-up possible now) |
| P01.S2.T3 | Classify data and retention | not registered (TODO by rule) | Deletion/anonymisation jobs, backup expiry as config | B15 |
| P01.S4.T1 | Prove mobile integration feasibility | TODO (named in P13.S1 row) | Native video, OIDC, push, billing, DeviceCheck/Play Integrity in dev builds | B13,B07,B04,B05,B08 |
| P01.S4.T3 | Baseline cost and observability | not registered (TODO by rule) | Cost baseline with real rates (job correlation is C under P03.S4.T2) | B03 |
| P01.S4.T4 | Set connection, recovery and background-work budgets | PARTIAL | Measured envelopes, per-endpoint admission budgets | B03 (P20) |
| P02.S3.T1 | Prototype learning | not registered (TODO by rule) | Video/transcript part of learning prototype | B05 |
| P02.S4.T1 | Test responsive layouts | not registered (TODO by rule) | Named reference devices; tablet/landscape viewports doable now | B09 |
| P02.S4.T3 | Validate with representative learners | not registered (TODO by rule) | Observe >=5 target learners | owner + learners |
| P03.S2.T1 | Separate development, staging and production | not registered (TODO by rule) | Separate envs, buckets, billing; staging banner doable now | B03,B06,B07 |
| P03.S2.T2 | Manage secrets and access | not registered (TODO by rule) | Secret store, workload identities, rotation | B03 |
| P03.S4.T1 | Connect the vertical slice | IN_PROGRESS | Reviewed owner lesson with scientific block on web + native dev builds | B01, B13/B07 |
| P04.S1.T1 | Implement registration and verification | IN_PROGRESS | IdP verification, enumeration and abuse controls | B04 |
| P04.S1.T2 | Implement login and recovery | IN_PROGRESS | OIDC redirect, native PKCE, recovery | B04, B13/B07 |
| P04.S4.T1 | Define age-appropriate defaults | not registered (TODO by rule) | Guardian-consent legal review | B15 / legal review |
| P05.S4.T1 | Validate the supplied curriculum package | not registered (TODO by rule) | Validate actual package with verified inclusions | B01,B02 |
| P07.S2.T2 | Implement adaptive playback | not registered (TODO by rule) | Adaptive playback | B05 |
| P07.S2.T3 | Protect and monitor media | not registered (TODO by rule) | Signed playback, callback validation, monitoring | B05 |
| P07.S4.T4 | Establish the AI-assisted production evaluation and reproducibility contract | not registered (TODO by rule) | Reviewer-approved evaluation set | B01 |
| P09.S2.T1 | Build MDCAT mock blueprints | PARTIAL | Verified MDCAT profile, PMDC outcome mapping; full mock needs sections outside SCOPE-01 | B02, owner scope |
| P09.S2.T2 | Build ECAT mock blueprints | PARTIAL | Verified ECAT combinations incl. English | B02, owner scope |
| P11.S2.T4 | Build and pass the multilingual search benchmark | not registered (TODO by rule) | Reviewer-graded benchmark queries | B16 |
| P13.S1.T1 | Configure application identities and variant builds | IN_PROGRESS (P13.S1 row) | Signed variant builds | B07,B13 |
| P13.S1.T2 | Implement native navigation and design | IN_PROGRESS (P13.S1 row) | TalkBack/VoiceOver/RTL/text-scaling on device | B13,B07,B09 |
| P13.S1.T3 | Integrate account and secure sessions | IN_PROGRESS (P13.S1 row) | Native OIDC, reinstall/backup tests | B04,B13/B07 |
| P13.S4.T1 | Test real devices | not registered (TODO by rule) | Real device testing | B09,B07,B13 |
| P13.S4.T2 | Establish compatible update behaviour | not registered (TODO by rule) | expo-updates runtime pin and OTA qualification | B07 |
| P13.S4.T3 | Prepare beta distribution | not registered (TODO by rule) | Signed test-track builds | B07 |
| P14.S2.T1 | Select and implement one merchant-approved gateway | not registered (TODO by rule) | Merchant gateway | B06,D03 |
| P14.S2.T2 | Verify payment outcomes server-side | not registered (TODO by rule) | Server-side outcome verification | B06,D03 (provider-neutral order ledger + fixture adapter possible; B06 lists sandbox adapter) |
| P14.S2.T3 | Handle retries and payment states | not registered (TODO by rule) | Payment state machine | B06,D03 (state machine with fixture adapter possible) |
| P14.S3.T1 | Review storefront payment requirements | not registered (TODO by rule) | Store billing review | B07,D04 |
| P14.S3.T2 | Validate store transactions | not registered (TODO by rule) | Store transaction validation | B07 |
| P14.S3.T3 | Reconcile cross-platform access | not registered (TODO by rule) | Cross-platform access | B06,B07 |
| P14.S4.T1 | Add refunds and source-isolated reconciliation | not registered (TODO by rule) | Refunds and reconciliation | B06 |
| P14.S4.T2 | Provide receipts and purchase history | not registered (TODO by rule) | Receipts and purchase history | B06 |
| P14.S4.T3 | Test adverse payments and conversion races | not registered (TODO by rule) | Adverse payment tests | B06 |
| P14.S6.T1 | Integrate iOS DeviceCheck and App Attest | PARTIAL (P14.S6 stage) | DeviceCheck/App Attest | B07 |
| P14.S6.T2 | Integrate Android Play Integrity and device recall | PARTIAL (P14.S6 stage) | Play Integrity and recall | B08,B07 |
| P17.S1.T1 | Provision infrastructure as code | not registered (TODO by rule) | Infrastructure as code | B03,D14 |
| P17.S1.T2 | Configure edge and ingress | not registered (TODO by rule) | CDN, TLS, edge rate controls | B03 |
| P17.S1.T3 | Configure production state services | not registered (TODO by rule) | Managed DB HA, pooler, backups | B03 |
| P17.S2.T1 | Scale API and web replicas | not registered (TODO by rule) | Replica scaling | B03 |
| P17.S2.T3 | Prepare scheduled exam peaks | not registered (TODO by rule) | Pre-warm and quota checks | B03 |
| P17.S2.T4 | Validate global connection and recovery traffic budgets | not registered (TODO by rule) | Global connection budget validation | B03 |
| P17.S3.T2 | Automate safe releases | PARTIAL | Health-gated staged deploys | B03 |
| P17.S4.T1 | Restore backups and media in isolation | not registered (TODO by rule) | Isolated restore drill | B03,B05 |
| P17.S4.T2 | Exercise infrastructure failures | not registered (TODO by rule) | Infra failure drills | B03 |
| P17.S4.T3 | Write service runbooks | PARTIAL | Restore, payment, attestation, exam-outage runbooks | B03-B08, owner outage policy |
| P18.S3.T2 | Exercise access and deletion requests | PARTIAL | Deletion/anonymisation execution | B15 |
| P18.S3.T3 | Finalise published policies | not registered (TODO by rule) | Reviewed policies | B15, legal review |
| P18.S4.T1 | Run an independent security review | not registered (TODO by rule) | Independent security review | owner: qualified reviewer |
| P18.S4.T3 | Close release-blocking defects | not registered (TODO by rule) | Close findings of the independent review | P18.S4.T1 |
| P19.S2.T2 | Verify native devices and interruptions | not registered (TODO by rule) | Native interruption tests | B09,B14,B07,B13 |
| P19.S2.T3 | Verify accessibility manually | PARTIAL (P19 a11y row) | Manual screen-reader and 200% zoom review by a person; automatable gaps under P02.S4.T2 | a person (owner to arrange) |
| P19.S4.T1 | Run representative user acceptance | not registered (TODO by rule) | UAT with invited users | owner + deployment B03 |
| P19.S4.T2 | Resolve and retest defects | not registered (TODO by rule) | UAT defects | P19.S4.T1 |
| P19.S4.T3 | Freeze a tested release candidate | PARTIAL | Image digests, native builds (images buildable now: P03.S3.T2) | B03,B07 |
| P20.S1.T3 | Validate generator and provider limits | not registered (TODO by rule) | Funded load environment run | B03 |
| P20.S2.T1 | Run the 5,000-active-user baseline | not registered (TODO by rule) | Funded load environment run | B03 |
| P20.S2.T2 | Run start, submit and deadline burst scenarios | not registered (TODO by rule) | Funded load environment run | B03 |
| P20.S2.T3 | Run open-arrival and headroom tests | not registered (TODO by rule) | Funded load environment run | B03 |
| P20.S3.T1 | Test failures and recovery waves under load | not registered (TODO by rule) | Funded load environment run | B03 |
| P20.S3.T2 | Run a soak test | not registered (TODO by rule) | Funded load environment run | B03 |
| P20.S3.T3 | Verify frontend/native performance against device budgets | not registered (TODO by rule) | Device budget measurements | B09,B03 |
| P20.S4.T1 | Resolve measured bottlenecks | not registered (TODO by rule) | Funded load environment run | B03 |
| P20.S4.T2 | Produce the operating cost model | not registered (TODO by rule) | Funded load environment run | B03 |
| P20.S4.T3 | Publish the capacity certificate internally | not registered (TODO by rule) | Funded load environment run | B03 |
| P21.S1.T1 | Complete the requirement traceability review | not registered (TODO by rule) | Final traceability review | needs P21 inputs (B01 RCS etc.) |
| P21.S1.T2 | Demonstrate the complete real-content portal | not registered (TODO by rule) | Real-content demonstration | B01,B10,B06 |
| P21.S1.T3 | Record readiness without passing blocked requirements | not registered (TODO by rule) | Final readiness record | all gates |
| P21.S2.T1 | Deliver operating documentation | not registered (TODO by rule) | Deployment/backup/restore guides (setup guide under P03.S1.T3) | B03 |
| P21.S2.T2 | Deliver content intake templates | not registered (TODO by rule) | Validated sample package needs approved content | B01 |
| P21.S2.T3 | Deliver reproducible release evidence | not registered (TODO by rule) | Signed builds, artifact hashes | B03,B07 |
| P21.S3.T1 | Verify production catalogue integrity | not registered (TODO by rule) | Production catalogue integrity | B01 |
| P21.S3.T2 | Rehearse a new-course import | not registered (TODO by rule) | New-course import rehearsal on real material | B01 |
| P21.S3.T3 | Finalise the handover register | not registered (TODO by rule) | Handover register | all gates |
| P22.S1.T2 | Map content to outcomes and tests | P22.S1 stage rows | Mapping to approved profiles | B01,B02 |
| P22.S1.T3 | Approve the launch manifest and select the RCS | P22.S1 stage rows | Approve manifest, select RCS | owner, B01 |
| P22.S2.T1 | Produce lesson and video packages | not registered (TODO by rule) | Reviewed production | B01,B05 |
| P22.S2.T2 | Populate the approved question bank | not registered (TODO by rule) | Reviewed production | B01 |
| P22.S2.T3 | Verify academic completeness | not registered (TODO by rule) | Reviewed production | B01 |
| P22.S2.T4 | Measure production throughput and forecast the catalogue | not registered (TODO by rule) | Reviewed production | B01 |
| P22.S3.T1 | Run content-rendering regression | not registered (TODO by rule) | Academic release | B01, devices |
| P22.S3.T2 | Publish approved course releases | not registered (TODO by rule) | Academic release | B01 |
| P22.S3.T3 | Obtain academic acceptance | not registered (TODO by rule) | Academic release | B01 |
| P23.S1.T1 | Validate live integrations | not registered (TODO by rule) | Live launch work | B03-B08 |
| P23.S1.T2 | Complete store submissions | not registered (TODO by rule) | Live launch work | B07 |
| P23.S1.T3 | Run go-live review on the release manifest | not registered (TODO by rule) | Live launch work | B03,B07 |
| P23.S2.T1 | Launch an invited production pilot | not registered (TODO by rule) | Live launch work | launch |
| P23.S2.T2 | Expand through measured cohorts | not registered (TODO by rule) | Live launch work | launch |
| P23.S2.T3 | Establish the incident cadence | not registered (TODO by rule) | Live launch work | launch |
| P23.S3.T1 | Measure actual value and cost | not registered (TODO by rule) | Live launch work | launch data |
| P23.S3.T2 | Maintain academic and software versions | not registered (TODO by rule) | Live launch work | launch |
| P23.S3.T3 | Choose the next expansion from evidence | not registered (TODO by rule) | Live launch work | owner, evidence |
| W00.S1.T1 | Freeze the student outcomes and exclusions | RECORDED (owner freeze pending) | Owner freeze of outcomes/exclusions | WA-D12 (owner) |
| W00.S1.T2 | Select the first academic slice | TODO (not in register; audit: blocked) | Pick subject/grade/chapter/language/type from owner data; publish supported matrix | WA-D01, B01 |
| W00.S1.T3 | Approve the student-facing assessment claims | TODO (not in register; audit: blocked) | Owner/academic approval; Urdu copy; S+P+U=M copy (see W07.S1.T1) | Owner approval; B01 (Urdu, reviewers) |
| W00.S2.T1 | Complete source intake | TODO (not in register; audit: blocked) | Board/session refs, question ownership, draft rubrics, reviewer assignments; owner acceptance | B01, B02, owner |
| W00.S2.T2 | Register real-script permissions and coverage | TODO (not in register; audit: blocked) | Consented scripts, minimisation, coverage and grouping record | B10 |
| W00.S2.T3 | Name the operational owners | TODO (not in register; audit: blocked) | Named adjudication/review/provider/privacy/support/incident owners with availability | Owner decision: named owners (B01) |
| W00.S2.T4 | Approve processor terms and processing location | TODO (not in register; audit: blocked) | Per-provider PROCESSOR_APPROVED record | B10, WA-D14 |
| W00.S3.T2 | Resolve policy defaults with accountable owners | IMPLEMENTED as records (row W00.S3.T1-T2) | Owner/lead approval of each WA-D | WA-D01..WA-D15 (owner) |
| W00.S3.T3 | Establish a dependency-based estimate | TODO (not in register; audit: partial) | Estimate; final one after real-script spikes and measured annotation/review | B10; owner staffing. Partial: initial engineering estimate |
| W01.S1.T2 | Encode board and custom form rules | TODO (not in register; audit: blocked) | Reviewer-read board patterns; composite child contracts | B02, WA-D15, B01 (named reviewer) |
| W01.S1.T3 | Publish only reviewed content | TODO (W01 stage row; audit: partial) | Outcome mapping gate (books print no SLO codes); academic approval | B01 |
| W01.S3.T1 | Build the real-script evaluation inventory | TODO (not in register; audit: blocked) | Inventory of consented real scripts | B10 |
| W01.S3.T2 | Produce teacher labels and adjudications | TODO (not in register; audit: blocked) | Two independent teacher marks and adjudication on real scripts | B10, B01 |
| W01.S3.T3 | Freeze development/calibration/held-out splits | TODO (not in register; audit: blocked) | Real-data splits, preregistered counts and thresholds | B10, WA-D06 |
| W02.S1.T1 | Model immutable evidence and attempts | TODO (not in register; audit: partial) | Retention/deletion references across records | B15, WA-D10 |
| W02.S1.T2 | Model assessment and review provenance | TODO (not in register; audit: partial) | Reading joint alternatives; explicit human-protection marker for AI publication | B10/WG10. Partial: fixture-backed reading-record model |
| W02.S3.T1 | Run bounded real-script reading spikes | TODO (not in register; audit: blocked) | Spikes on accepted real scripts | B10, W00.S2.T4 |
| W02.S3.T2 | Validate storage and worker foundations | TODO (not in register; audit: blocked) | Real object storage, one real end-to-end job, rolling overlap | B03, B10 |
| W02.S3.T3 | Record implementation decisions | TODO (not in register; audit: blocked) | Adapter/model/queue choices from spike measurements | B10, WA-D05 |
| W03.S1.T2 | Implement native capture/import | PARTIAL (code only) | Device verification | B14 (B07, B09, B13) |
| W03.S1.T3 | Implement conservative transformations | PARTIAL (web) | Qualify on real faint-ink/pencil scripts; mobile on a device | B10, B14 |
| W03.S1.T4 | Implement progressive upload and the capture resolution policy | TODO (not in register; audit: partial) | Measured resolution preset and higher-detail fallback qualified on phones | WA-D13, B09, B14 |
| W03.S3.T1 | Implement private direct uploads | IMPLEMENTED (dev store) | Short-lived signed direct-to-object-store upload sessions | B03. Partial: S3-compatible adapter against a local emulator |
| W04.S1.T2 | Freeze form and choice rules | PARTIAL | Section choices; counted vs extra answers | WA-D03, WA-D15 (decision-briefs/choice-sections.md) |
| W04.S1.T4 | Define mixed board-paper parent and child contracts for R3 | TODO (audit: not started) | CompositeBoardForm/Attempt | WA-D15, B02 |
| W05.S1.T1 | Implement the qualified reading adapter | TODO (W05 stage row PARTIAL) | Reading adapter with regions and alternatives bound to evidence hash | B10. Partial: fixture reading-record contract |
| W05.S1.T2 | Reconcile mapping and unreadable regions | TODO (W05 stage row) | Detect missing continuations and contradictory reading outputs | B10 |
| W05.S1.T3 | Calibrate escalation signals | TODO (W05 stage row) | Calibration labels and observable signals | B10, WA-D06 |
| W05.S1.T4 | Implement the alternative-invariance and blank-evidence rules | TODO (W05 stage row) | Joint-variant invariance via a qualified assessor | B10. Partial: invariance validator on fixture variants |
| W06.S3.T1 | Forecast and monitor review demand | PARTIAL | Recheck demand in admission; escalation/audit terms; active review minutes | WA-D08, B10. Partial: record active marking minutes |
| W06.S3.T3 | Train and qualify reviewers | PARTIAL | Approved examples, discussion threads, periodic rounds | B01, WA-D08. Partial: discrepancy discussion threads |
| W07.S1.T4 | Publish compatible composite board-paper results for R3 | TODO (audit: not started) | Composite aggregate results | WA-D15, B02 |
| W07.S3.T3 | Validate explanation language | TODO (not in register; audit: blocked) | Subject-reviewer terminology checks; Urdu/Roman Urdu feedback | B01 |
| W08.S1.T1 | Configure transparent assessment plans | PARTIAL | Cost-backed weights | WA-D07, B06 |
| W08.S2.T3 | Verify processor and consent controls | TODO (not in register; audit: blocked) | Check approved W00.S2.T4 record against deployed config | B10, WA-D14 |
| W08.S3.T1 | Apply versioned retention policies | TODO (not in register; audit: blocked) | Approved periods, scheduler, scan-expiry display | B15, WA-D10 |
| W08.S3.T2 | Delete across processing systems | TODO (not in register; audit: blocked) | Tombstones and deletion across stores and jobs | B15 |
| W08.S3.T3 | Verify restore and incident handling | TODO (not in register; audit: blocked) | Tombstone replay after restore; access-incident exercise | B15, B03 |
| W09.S1.T2 | Measure workload and cost distributions | TODO (not in register or audit) | Real traffic samples and provider prices | B03, B10, B06 |
| W09.S2.T1 | Run the mixed 5,000-user workload | TODO (not in register or audit) | Load run on real infrastructure | B03 |
| W09.S2.T2 | Run sustained and burst script arrivals | TODO (not in register or audit) | Burst runs | B03 |
| W09.S2.T3 | Exercise constrained clients and networks | TODO (not in register or audit) | Low-memory phones, weak links | B09, B14 |
| W09.S3.T1 | Run failure and restore exercises | TODO (not in register or audit) | DB/object restore, deployment restarts | B03 |
| W09.S3.T2 | Staff and rehearse operations | TODO (not in register or audit) | Real staffing rehearsal | B01, owner |
| W09.S3.T3 | Approve cost and capacity limits | TODO (not in register or audit) | Measured limits, owner approval | WA-D07, WA-D08, B03, B10 |
| W10.S1.T1 | Execute R0 on real learner scripts | TODO (not in register or audit) | R0 pilot on real scripts | B10, B01 |
| W10.S1.T2 | Compare teachers, readers and graders | TODO (not in register or audit) | Analysis on real data | B10, B01 |
| W10.S1.T3 | Validate operational learning value | TODO (not in register or audit) | Pilot findings | B10, B01 |
| W10.S2.T1 | Freeze candidate policies before the hold-out run | TODO (not in register or audit) | Frozen model/prompt/routing/thresholds | B10, WA-D06 |
| W10.S2.T2 | Apply accuracy, uncertainty and coverage gates | TODO (not in register or audit) | Held-out gate results | B10, WA-D06 |
| W10.S2.T3 | Authorise only passing short-answer slices | TODO (not in register or audit) | Qualification records | B10, WA-D06 |
| W10.S2.T4 | Verify sample feasibility and per-slice minimums | TODO (not in register or audit) | Preregistered feasibility record | B10, WA-D06 |
| W10.S3.T1 | Qualify required long-answer scopes for R2 | TODO (not in register or audit) | Long-answer qualification | B10, B01 |
| W10.S3.T2 | Qualify numerical and diagram routes for R3 | TODO (not in register or audit) | Numerical/diagram qualification | B10, WA-D11 |
| W10.S3.T3 | Qualify larger and official-pattern forms for R3 | TODO (not in register or audit) | Official-pattern form qualification | B10, B02, WA-D15 |
| W10.S3.T4 | Qualify the complete mixed board-paper journey for R3 | TODO (not in register or audit) | Composite journey qualification | WA-D15, B02, B10, B14 |
| W11.S1.T1 | Audit the complete release manifest | TODO (not in register or audit) | Audit before P21/P23 | WG10/B10, B03. Partial: written capability section in manifest |
| W11.S1.T2 | Verify the cross-platform real-data journey | TODO (not in register or audit) | Real-content web/Android/iOS run | B01, B10, B14 |
| W11.S1.T3 | Publish accurate help and terms | TODO (not in register or audit) | Written help and terms incl. retention and allowances | B15, WA-D07, owner/legal. Partial: draft help articles |
| W11.S2.T1 | Enable a bounded learner cohort | TODO (not in register or audit) | Live cohort | B03, WG10 |
| W11.S2.T2 | Audit released marks and upheld rechecks | TODO (not in register or audit) | Live sampling audits | B03, B10, WA-D06 |
| W11.S2.T3 | Rehearse rollback and student remediation | TODO (not in register or audit) | Rehearsal of disabling a live automatic route | B10, B03 |
| W11.S2.T4 | Run the canary drift monitor | TODO (not in register or audit) | Consented canary baseline | B10 |
| W11.S3.T1 | Deliver operator and academic runbooks | TODO (not in register or audit) | Runbooks, named owners, controlled exercise | Owner (W00.S2.T3), B15, B10. Partial: queue/assignment/rescan/rubric runbooks |
| W11.S3.T2 | Establish requalification triggers | TODO (not in register or audit) | Impact review and invalidation of qualification records | B10 (W10) |

## A: implemented and verified (197)

| Task | Title | Evidence | Remaining (external) |
|---|---|---|---|
| P00.S1.T2 | Define release boundaries | RELEASE_CHECKLIST three readiness states; guarded by apps/api/tests/test_readiness_claims.py (READINESS-01) | Owner acceptance |
| P00.S2.T1 | Create the external dependency register | BLOCKERS.md B01-B16 with first blocked work and input owner; read by test_readiness_claims.py | Lead times per input (register text still says B01-B15) |
| P00.S3.T1 | Create the implementation register | Register, RESUME_STATE, DECISIONS, BLOCKERS, DEPENDENCIES, RELEASE_CHECKLIST exist | Keep current (several stale rows, see report) |
| P00.S3.T4 | Maintain task dependencies and evidence-gate scopes | DEPENDENCIES.md Section 18 waves (doc) | Per-task estimates after spikes; wave states dated 2026-10-06 |
| P01.S1.T1 | Pin the supported stack | docs/project/STACK.md; uv.lock, pnpm-lock.yaml; client minimums in test_client_policy.py | Minimum OS choice D08 |
| P01.S1.T4 | Define the configuration and artifact qualification model | config.py, web instrumentation.ts; test_config.py, test_deployed_roles.py, test_release.py | Deployed evidence |
| P01.S2.T1 | Define entity relationships and constraints | Models/migrations across all modules; alembic check in CI | ComparisonCohortSnapshot (with P12.S2.T3); purchase-bound TrialCredit (B06) |
| P01.S3.T2 | Specify mutation and cutoff semantics | IMPL-17, ATTEMPT-STATES-01; test_attempts.py, test_start_clock.py, test_persistence_ledger.py | Purchase-transition serialization |
| P01.S3.T3 | Define background processing | DB job tables with backoff/dead letters/requeue: test_bulk_import.py, test_support_reliability.py, test_written_auto_recovery.py | No generic outbox (ElasticMQ in compose unused); job correlation is P03.S4.T2 |
| P01.S3.T4 | Define the content schema and renderer capability contract | Block registry, CLIENTS-01, COMPAT-01; test_client_compatibility.py, test_content_compat_scenario.py | Gate uses code constant (see P13.S1.T4) |
| P02.S1.T1 | Define the student navigation | Web header Learn/Practice/Search/Help + account; mobile tabs; e2e/visible-actions.spec.ts crawl | Mocks/Revision under Practice, not top level (unrecorded design choice) |
| P02.S1.T2 | Define the admin navigation | Studio/admin show permitted actions; test_authorization_matrix.py, test_staff_actions_authz.py; staff crawl | - |
| P02.S2.T3 | Define motion and theme rules | Reduced motion + dark theme (globals.css, SETTINGS-01); e2e/settings.spec.ts | - |
| P02.S3.T2 | Prototype the exam room and honest persistence states | Exam room built (FLAGS-01, RECEIPT-01); e2e/practice.spec.ts states, tolerance, flags | - |
| P02.S3.T3 | Prototype actionable results | Result summary, meters, plan shortfall; test_result_summary.py, test_study_plan.py | - |
| P03.S1.T1 | Scaffold the application workspace | Monorepo incl. apps/mobile (IMPL-03); CI jobs per app | Row remaining "apps/mobile" stale |
| P03.S2.T3 | Create environment validation | config validator, /healthz,/readyz; test_config.py, test_deployed_roles.py | Secret store |
| P03.S3.T1 | Establish change checks | .github/workflows/ci.yml path-filtered jobs | - |
| P03.S3.T3 | Store meaningful test evidence | Playwright trace/screenshot on failure; report artifact, 7-day retention (ci.yml) | - |
| P03.S4.T3 | Verify clean installation | CI e2e: fresh checkout, alembic upgrade head, catalogue import, dev seeds; conftest refuses non-_test DB | Docs only (with P03.S1.T3) |
| P04.S1.T3 | Add session and device controls | test_sessions.py, test_session_mid_attempt.py, e2e/auth.spec.ts, e2e/trial-devices.spec.ts | Refresh rotation/reuse at IdP; device check |
| P04.S2.T1 | Enforce roles in API operations | permissions.py; test_authorization_matrix.py, test_account_boundaries.py, test_written_authz.py | Row remaining stale |
| P04.S2.T3 | Implement entitlement checks | test_lesson_access.py, test_entitlement_scope.py, test_access_grants.py, e2e/admin-access.spec.ts | Commercial grants (row wrongly says package scoping pending) |
| P04.S3.T1 | Collect learning preferences | PUT /v1/me/profile; e2e/auth.spec.ts register+onboard | Device check |
| P04.S3.T2 | Configure personal study settings | test_study_settings.py; e2e/settings.spec.ts | Video quality; mobile device check |
| P04.S3.T3 | Implement account lifecycle | test_reauth.py, test_account_suspension.py, test_privacy.py | Reviewed policy text |
| P04.S4.T2 | Record consent and preference changes | Versioned consents; test_identity.py | Reviewed policy texts |
| P04.S4.T3 | Verify account boundaries | test_account_boundaries.py | - |
| P05.S1.T1 | Build the curriculum hierarchy | curriculum/models.py; test_importer.py, test_catalogue_api.py, test_catalogue_identity.py | Boards/sessions only as inclusion scopes and source metadata (sessions UNKNOWN) |
| P05.S1.T2 | Add learning outcomes and prerequisites | test_concepts.py | Real outcomes |
| P05.S2.T1 | Implement inclusion records | INCLUSION-01; test_inclusion.py, test_dashboard.py | Real mappings |
| P05.S2.T2 | Implement mapping review | INCLUSION-01; test_inclusion.py, test_dashboard.py | Real mappings |
| P05.S2.T3 | Produce coverage dashboards | INCLUSION-01; test_inclusion.py, test_dashboard.py | Real mappings |
| P05.S3.T1 | Build versioned exam profiles | EXAMPROFILE-01; test_exam_profiles.py | Verified official profiles |
| P05.S3.T2 | Implement subject combinations | EXAMPROFILE-01; test_exam_profiles.py | Verified official profiles |
| P05.S3.T3 | Add profile publication controls | EXAMPROFILE-01; test_exam_profiles.py | Verified official profiles |
| P05.S4.T2 | Test future-region extensibility | test_region_isolation.py | - |
| P05.S4.T3 | Verify profile changes | test_profile_changes.py | Browser check needs a published pattern (see P09.S2.T3) |
| P06.S1.T1 | Build catalogue management | test_catalogue_admin.py | - |
| P06.S1.T3 | Support safe concurrent editing | test_content_workflow.py::test_autosave_detects_concurrent_edits; e2e/studio.spec.ts | - |
| P06.S2.T1 | Implement structured import formats | test_content_import.py, test_import_xlsx.py, test_import_refs.py, test_media_manifest.py, test_bulk_import.py | W01 script-evaluation manifests |
| P06.S2.T2 | Implement preview and error recovery | test_content_import.py; e2e/studio.spec.ts | - |
| P06.S2.T3 | Add safe source-document intake | test_source_intake.py | Durable private storage |
| P06.S3.T1 | Build preview across delivery surfaces | test_surface_preview.py | - |
| P06.S3.T3 | Implement correction and retirement | test_rollback_export.py, test_mcq_corrections.py | Release-level rollback comes with P06.S3.T2 |
| P06.S4.T1 | Protect file intake | test_upload_scanning.py | Scanner daemon deployment |
| P06.S4.T3 | Rehearse the complete staff workflow | test_staff_workflow_rehearsal.py | Real-material rehearsal |
| P07.S1.T1 | Build structured content blocks | test_lesson_blocks.py; e2e/lessons.spec.ts | Devices; typeset equations via P01.S4.T2 |
| P07.S1.T3 | Add lesson completion checkpoints | test_checkpoints.py; e2e/lessons.spec.ts checkpoint | - |
| P07.S2.T1 | Integrate resumable/direct uploads | test_media_uploads.py | Provider adapter, short-lived credentials |
| P07.S2.T4 | Build the owned master archive and retention rules | test_assets.py, test_media_manifest.py | Delivery-copy re-ingest |
| P07.S3.T1 | Add captions and transcripts | test_lectures.py (WebVTT per language) | Captions edited by re-upload only; terms review |
| P07.S3.T2 | Add chapter markers and bookmarks | test_lecture_markers.py, test_lectures.py | Learner timestamp bookmarks need the player |
| P07.S3.T3 | Provide low-bandwidth study alternatives | test_lesson_blocks.py; e2e/settings.spec.ts data saver | Optional audio-only assets |
| P07.S4.T1 | Build storyboard records and exports | test_storyboards.py | - |
| P07.S4.T2 | Specify every scene precisely | test_storyboards.py | - |
| P07.S4.T3 | Review finished media before release | test_lectures.py | Reconcile final video with script; approvals |
| P08.S1.T1 | Implement single-best-answer MCQs | test_mcq_items.py, test_question_diagrams.py, test_passages.py | - |
| P08.S1.T2 | Add explanations and sources | test_mcq_items.py | - |
| P08.S1.T3 | Add quality metadata | test_mcq_items.py; empirical stats separate (test_item_stats.py) | - |
| P08.S2.T1 | Build question review | test_mcq_items.py::test_review_checklist_publication_and_key_isolation; e2e/studio.spec.ts | - |
| P08.S2.T2 | Validate option behaviour | test_mcq_items.py, test_question_diagrams.py, test_passages.py | - |
| P08.S2.T3 | Isolate answer keys | test_attempts.py::test_attempt_payload_never_contains_keys, test_study_packs.py, test_exposure.py | Row stale |
| P08.S3.T2 | Support question variants | test_mcq_items.py, test_import_refs.py | Approved variants |
| P08.S3.T3 | Manage availability and exposure | test_mock_pools.py | Cross-learner exposure caps need data |
| P08.S4.T1 | Process error reports and quarantine by defect type | test_mcq_corrections.py | - |
| P08.S4.T2 | Implement versioned corrections | test_mcq_corrections.py | - |
| P08.S4.T3 | Evaluate question statistics | test_item_stats.py | Thresholds for academic lead review |
| P09.S1.T1 | Build topic and chapter tests | test_attempts.py, test_practice_config.py; e2e/practice.spec.ts | - |
| P09.S3.T2 | Handle insufficient pools honestly | test_attempts.py::test_availability_and_honest_pool_shortage; builder shows available count | - |
| P09.S4.T1 | Preview forms as a reviewer | test_form_preview.py | - |
| P09.S4.T2 | Validate generator properties | test_scoring_properties.py, test_generator_properties.py | - |
| P09.S4.T3 | Publish test availability | test_form_replacement.py, test_client_compatibility.py | - |
| P10.S1.T1 | Implement the attempt state machine | ATTEMPT-STATES-01; test_attempts.py, test_scoring_recovery.py | Whole-attempt void action |
| P10.S1.T2 | Implement authoritative editing and admission deadlines | test_attempts.py deadline tests; web pre-flush at D-5s in attempt-runner.tsx | Row says UI pre-flush pending (stale) |
| P10.S1.T3 | Control simultaneous sessions | test_attempt_handoff.py | Device check |
| P10.S2.T1 | Persist answer revisions and recover durable receipts | test_attempts.py::test_save_dispositions | - |
| P10.S2.T2 | Build local recovery queues | e2e/practice.spec.ts reload/outage | Mobile queue code only (host test folded into P13.S2.T2) |
| P10.S2.T3 | Define offline fairness and tolerance | test_attempts.py; e2e/practice.spec.ts tolerance notice | Published outage/reschedule policy |
| P10.S3.T1 | Implement atomic final-answer submission and expiry | test_attempts.py | - |
| P10.S3.T2 | Implement deterministic grading and adjudication | test_scoring_properties.py, test_attempts.py::test_scoring_rules | - |
| P10.S3.T3 | Make result creation recoverable | test_scoring_recovery.py | - |
| P10.S3.T4 | Apply correction overlays and cumulative score versions | test_mcq_corrections.py, test_form_replacement.py | Row remaining stale (both done) |
| P10.S4.T1 | Run persistence failure cases | test_persistence_ledger.py | - |
| P11.S1.T1 | Build the public product site | e2e/public-site.spec.ts | Live PORTAL_PUBLIC_ORIGIN |
| P11.S1.T2 | Build the personal dashboard | test_dashboard.py; e2e/journeys.spec.ts, accessibility.spec.ts | Syllabus coverage data |
| P11.S2.T2 | Build personal study tools | test_study_tools.py; e2e/lessons.spec.ts | Timestamp bookmarks (row wrongly says mobile tools not built) |
| P11.S2.T3 | Add content search | test_search.py; e2e/search.spec.ts | Owner alias terms; transcripts |
| P11.S3.T2 | Build the exam room | test_attempt_flags.py; e2e/practice.spec.ts flags | Device budgets |
| P11.S4.T1 | Optimise route rendering | e2e/payload-budget.spec.ts | Device budgets |
| P11.S4.T2 | Implement installable web support | e2e/pwa.spec.ts | Device install |
| P11.S4.T3 | Verify all visible actions | e2e/visible-actions.spec.ts | - |
| P12.S1.T1 | Build the versioned result summary | test_result_summary.py; e2e/practice.spec.ts | - |
| P12.S1.T2 | Build question review | test_review_lesson_links.py, test_result_release.py | - |
| P12.S1.T3 | Implement regrades, disputes and derived propagation | test_mcq_corrections.py, test_notebook_corrections.py | Cohort snapshot rebuild with P12.S2.T3 |
| P12.S2.T1 | Calculate exhaustive topic evidence | test_evidence_rules.py (300 random cases) | Verified outcome mapping |
| P12.S2.T4 | Version and explain complete evidence rules | test_evidence_rules.py | - |
| P12.S3.T2 | Implement spaced review rules | test_mistake_notebook.py | - |
| P12.S3.T3 | Add mixed revision practice | test_mixed_revision.py | - |
| P12.S4.T3 | Verify calculations and events | test_progress_checks.py | - |
| P14.S1.T1 | Define sellable products | test_products.py; e2e/products.spec.ts | Real products/prices |
| P14.S1.T2 | Implement entitlement and source-bound credit lifecycles | test_entitlement_scope.py, test_access.py, test_account_suspension.py | Refund/credit reversal |
| P14.S1.T3 | Configure transparent pricing | test_commerce_terms.py; e2e/pricing.spec.ts | Real terms/prices |
| P14.S5.T1 | Implement the one-time 30-day offer | test_access.py | Device-level consumption |
| P14.S5.T2 | Build the trial, device and claim ledger | test_trial_claims.py (fixture adapter) | Real device evidence |
| P14.S5.T3 | Reconcile all access sources | test_entitlement_scope.py, test_trial_claims.py | Purchase restore |
| P14.S5.T4 | Implement the corrected consolidated trial decisions | TRIAL-02; test_trial_claims.py, test_trial_acceptance.py, test_trial_matrix.py | 6 matrix rows blocked |
| P14.S6.T3 | Implement web and unsupported-device decisions | trial_devices.py web verdicts (account history, no fingerprinting); test_trial_claims.py | - |
| P14.S7.T1 | Recover claims with current eligibility checks | test_device_gate.py, test_trial_claims.py | Real devices |
| P14.S7.T2 | Enforce expiry and device authorization consistently | test_device_gate.py | Real devices |
| P14.S7.T3 | Build truthful trial and recovery notices | e2e/trial-devices.spec.ts, practice.spec.ts | - |
| P14.S8.T1 | Handle genuine shared-device cases | Scoped exceptions (TRIAL-02); trial false-block runbook; test_trial_claims.py, test_incident_rehearsals.py | Name the student operations lead |
| P14.S8.T2 | Define operational and privacy controls | test_trial_controls.py | Provider markers, retention |
| P14.S8.T3 | Verify the trial acceptance matrix | test_trial_matrix.py, test_trial_acceptance.py | Device/payment evidence |
| P14.S8.T4 | Report trial cost, decision quality and false blocks | test_trial_decisions.py | - |
| P15.S1.T1 | Define notification events and templates | test_notifications.py | - |
| P15.S1.T2 | Implement delivery adapters | test_notifications.py, test_service_degradation.py | Email sender, native push |
| P15.S1.T3 | Implement scheduling preferences | test_notifications.py | - |
| P15.S2.T1 | Build searchable support articles | test_help.py; e2e/support.spec.ts | Urdu translations need a reviewer |
| P15.S2.T2 | Add contextual guidance | test_help.py | - |
| P15.S2.T3 | Add service incident notices | test_help.py | Independent status hosting |
| P15.S3.T2 | Route academic corrections | test_support.py; e2e/support.spec.ts | - |
| P15.S3.T3 | Equip support staff safely | test_support_lookup.py; e2e/support.spec.ts | - |
| P15.S4.T1 | Handle delivery failures | test_support_reliability.py | Bounce webhooks |
| P15.S4.T2 | Prevent abuse of support channels | test_support_reliability.py | - |
| P15.S4.T3 | Rehearse common incidents | test_incident_rehearsals.py | - |
| P16.S1.T1 | Build the business overview | test_business_overview.py | External figures only |
| P16.S1.T2 | Build the academic overview | test_academic_overview.py | External figures only |
| P16.S1.T3 | Build the service overview | test_service_overview.py, test_operations.py | External figures only |
| P16.S2.T1 | Define the event dictionary | test_analytics_events.py | External figures only |
| P16.S2.T2 | Build funnel and retention reports | test_funnel_report.py | External figures only |
| P16.S2.T3 | Separate learning outcomes from engagement | test_learning_report.py | External figures only |
| P16.S2.T4 | Build the trial and paid cohort economics report | test_cohort_economics.py | External figures only |
| P16.S3.T1 | Manage feature flags and rollout | test_rollouts.py | - |
| P16.S3.T2 | Manage integrations and quotas | test_integrations.py | External figures only |
| P16.S3.T3 | Manage academic updates | test_academic_updates.py | External figures only |
| P16.S4.T1 | Build the audit explorer | test_audit_explorer.py | - |
| P16.S4.T2 | Provide controlled reporting exports | test_exports.py | External figures only |
| P16.S4.T3 | Validate owner operations | test_owner_validation.py, test_owner_operations.py | - |
| P17.S3.T1 | Configure operational alerts | test_operations.py; docs/runbooks/alerts.md | Paging integration |
| P17.S3.T3 | Implement rollback and feature disable | Feature switches test_operations.py; docs/runbooks/release-rollback.md | Last-known-good artifacts |
| P18.S1.T1 | Review the attack surface | docs/security/attack-surface.md (record) | Independent review |
| P18.S1.T2 | Verify authorisation systematically | test_authorization_matrix.py, test_role_revocation.py, test_search.py | Signed media |
| P18.S1.T3 | Review privileged workflows | test_privileged_workflows.py | - |
| P18.S2.T1 | Test common web/API risks | test_security_headers.py; e2e/security-headers.spec.ts, security-boundaries.spec.ts; ssrf-review.md, advisory-review.md | HSTS/TLS at edge (row says Next advisory record missing; advisory-review.md has it) |
| P18.S2.T2 | Test file and job abuse | test_import_abuse.py | - |
| P18.S2.T3 | Review supply chain and secrets | test_exposure.py, tools/test_sbom.py | Image scanning |
| P18.S3.T1 | Verify data minimisation | test_data_minimisation.py | Deployment processors |
| P18.S4.T2 | Validate incident response | test_account_suspension.py, test_results_postponement.py | Credential rotation rehearsal |
| P19.S1.T1 | Test new-to-returning learner journeys | e2e/journeys.spec.ts; test_unfinished_tests.py | Real content |
| P19.S1.T2 | Verify all assessment scopes and corrected boundary rules | test_scope_reconciliation.py | RCS run |
| P19.S1.T3 | Test owner operations end to end | test_owner_operations.py | Real refund |
| P19.S2.T1 | Verify supported browsers | e2e/browsers.spec.ts | Physical devices |
| P19.S3.T1 | Verify migration compatibility | test_upgrade_compatibility.py | Real rollback |
| P19.S3.T2 | Verify service degradation | test_service_degradation.py | Payments adapter |
| P19.S3.T4 | Verify content compatibility across supported clients | test_content_compat_scenario.py | Old build on a device |
| P20.S1.T1 | Prepare realistic data volume | test_volume_data.py | Academic bank, purchases |
| P20.S1.T2 | Build reproducible load scenarios | loadtest/practice_journey.py; test_loadtest_harness.py | Qualification run |
| P22.S1.T1 | Register the supplied material | content/source_registry.json; content/tools/test_identity.py; build_catalogue.py --check in CI | Rights; edition/session UNKNOWN |
| W00.S3.T1 | Define release evidence before implementation | RELEASE_CHECKLIST.md R0-R3 table (document task; no automated test applicable) | Owner acceptance of the map |
| W01.S2.T1 | Define bounded criteria | content/written.py validate_rubric/_unreachable/reconcile; test_written_records.py | Owner rubric imports |
| W01.S2.T3 | Review and version rubrics independently | test_content_workflow.py, test_rubric_adjudication.py | Academic approval of real rubrics |
| W02.S1.T3 | Model allowance and operational state | test_question_outcomes.py, test_access.py, test_permit_admission.py (COMPLETENESS-01) | None |
| W02.S2.T1 | Publish client/server schemas | packages/contracts drift check in CI; test_client_policy.py, test_evidence.py | None |
| W02.S2.T2 | Specify receipt and job transactions | test_written_attempts.py, test_publication_integrity.py, test_evidence.py | None |
| W02.S2.T3 | Specify privacy and academic boundaries | test_written_authz.py, test_written_injection.py | None |
| W03.S1.T1 | Implement browser capture/import | e2e practice.spec.ts (upload; PDF one page per PDF page); test_evidence.py; server renders PDF pages singly | Browser/device memory limits on reference devices |
| W03.S2.T1 | Add actionable quality checks | test_scan_quality.py, test_evidence.py; e2e glare retake | Threshold calibration on real scans |
| W03.S2.T3 | Check completeness and duplicates | Completeness before seal; exact per-attempt dedup (uq_written_file_attempt_hash) | Done: #200 NEAR-DUP-01 (flagged, never removed). Threshold calibration on real scans needs B10 |
| W03.S3.T2 | Implement bounded file validation | test_evidence.py, test_upload_scanning.py, test_written_injection.py | Linux memory caps verified in deployment |
| W03.S3.T3 | Verify interruption and concurrency recovery | e2e written-interruptions.spec.ts; test_written_attempts.py | Native run on a device |
| W04.S1.T3 | Present binding start terms | Builder terms; test_permit_admission.py, test_written_pilot.py, test_review_staffing.py | Max weighted choice reservation; measured transfer guidance |
| W04.S2.T1 | Separate writing and upload time | D/G/U and trust notice in builder; written-runner.tsx clock offset set once with ??= | Done: #199 WRITTEN-CONNECTION-01 (clock re-sync, offline notice, map re-saved, no hangs) |
| W04.S2.T2 | Implement the seal transaction | test_written_attempts.py, test_evidence.py (tamper), test_empty_seal.py, test_connection_holds.py | Parent/child composite identity (R3) |
| W04.S3.T1 | Resolve unsubmitted/expired drafts | test_written_attempts.py::test_nothing_is_admitted_after_the_upload_cutoff | Untimed recovery where policy permits |
| W04.S3.T2 | Implement authorised readability rescans | test_rescans.py, test_rescan_corrections.py, test_pr32_corrections.py; e2e practice clearer copy | Mobile rescans on a device |
| W05.S2.T1 | Build constrained assessment prompts/inputs | test_written_automatic.py | Real provider prompt |
| W05.S2.T2 | Validate all academic arithmetic | test_written_automatic.py, test_written_marking.py | None |
| W05.S2.T3 | Route unsupported reasoning safely | test_academic_review.py; e2e written-results.spec.ts | Automatic detection |
| W05.S3.T1 | Add retries and reconciliation | test_written_automatic.py, test_written_auto_recovery.py | Provider-side idempotency |
| W05.S3.T2 | Fence publication and record provenance | test_written_auto_provenance.py; no AI publication path | Fenced AI writer after WG10; pricing usage |
| W05.S3.T3 | Verify controlled failure behaviour | test_written_automatic.py, test_written_auto_provenance.py | Real provider failure modes |
| W06.S1.T1 | Display complete evidence and rubric context | test_written_marking.py, test_detail_view.py; e2e practice teacher-marks journey | Reading alternatives |
| W06.S1.T2 | Implement safe assignment and decisions | Leases and CAS (test_written_marking.py); review_router.py has no reassign/release endpoint | Done: #198 CASE-HANDBACK-01 (give back; adjudicator frees with MFA and a reason) |
| W06.S2.T1 | Add a clear recheck request flow | test_recheck.py; e2e written-results.spec.ts | None |
| W06.S2.T2 | Implement authorised score corrections | test_recheck.py, test_publication_integrity.py, test_rubric_adjudication.py; in-app notices | Email and push delivery |
| W06.S2.T3 | Process rubric adjudications across attempts | test_rubric_adjudication.py, test_w06_review.py, test_pr36_review.py; e2e adjudication.spec.ts | Production-scale load evidence |
| W06.S2.T4 | Classify readability, new-content and indeterminate rescans | test_rescans.py, test_pr32_corrections.py; e2e practice clearer-copy journey | None |
| W07.S1.T1 | Build marks and status presentation | written-runner.tsx, mobile written-result.tsx; e2e pending/unavailable cases | Done: #196 RESULT-ARITHMETIC-01 (S + P + U = M, assessor scope, work status). Exports and notifications don't carry P and U yet |
| W07.S1.T3 | Respect answer-release policies | test_model_answers.py | Reviewed worked answers |
| W07.S2.T1 | Provide targeted next steps | test_next_steps.py, test_review_lesson_links.py; e2e practice Next step | Real misconceptions |
| W07.S2.T2 | Add score and attempt history | test_written_history.py; e2e written-results.spec.ts | Device check |
| W07.S2.T3 | Isolate written learning signals | test_written_signals.py | None |
| W07.S3.T2 | Test interrupted processing journeys | test_written_interruptions.py; e2e written-receipts.spec.ts | Native restart on a device |
| W08.S1.T2 | Implement atomic allowance transitions | test_access.py, test_permit_admission.py, test_question_outcomes.py, test_empty_seal.py | Finite remedy deadlines and escalation automation |
| W08.S2.T1 | Verify end-to-end authorisation | test_written_authz.py, test_authorization_matrix.py | Signed URLs/region ownership once they exist |
| W08.S2.T2 | Test malicious inputs and model boundaries | test_written_injection.py, test_evidence.py | Real model prompt-injection evaluation |
