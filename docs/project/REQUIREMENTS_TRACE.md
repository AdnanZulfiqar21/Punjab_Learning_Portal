# REQUIREMENTS TRACE (P00.S1.T1)

Roadmap task **P00.S1.T1, "Register the owner requirements"** (roadmap §8, P00.S1). Written 2026-10-21. This file traces each requirement to roadmap phases and task IDs, to acceptance scenarios, and to the record that holds its current status. It is a record. It does not approve anything: it settles no Section 17 or Section 20.19 decision, passes no gate and changes no task state. Task and gate state stay in `IMPLEMENTATION_REGISTER.md`, settled choices in `DECISIONS.md` and external inputs in `BLOCKERS.md`.

**Conventions**

- "Roadmap" means `Road Map/Punjab_Learning_Portal_Master_Roadmap_v2.2_Integrated_Written_Assessment.md`, and § refers to its sections.
- AC means a core acceptance scenario (§9) and WA-AC a written one (§20.18). The roadmap marks every one NOT RUN. Any evidence for them is in the register, `TRIAL_ACCEPTANCE_MATRIX.md` or the test suites.
- A status pointer names an `IMPLEMENTATION_REGISTER.md` row by its Task label, because the register has no row numbers. "Not registered" means TODO under the register's rule.
- As P00.S1.T1 requires, the requirements are in three groups: (a) owner requirements, (b) enhancements the roadmap added, and (c) owner decisions that are still open, with their proposed defaults.

## (a) Owner requirements

These are stated as owner requirements in the roadmap: the owner brief (§1), the trial requirement (§16.1), the written-module brief (§20.1) and the P00.S1.T1 list.

| ID | Owner requirement (roadmap source) | Phases / tasks | Acceptance | Status pointer |
|---|---|---|---|---|
| OR01 | Academic data before implementation. The owner supplies sources first; inventory, validation and Punjab/exam mapping (P22.S1) come before the application is built. Demo lessons and invented MCQs are never a substitute (§1, §2.3, P00.S1.T1) | P22.S1.T1–T3, W00.S2.T1–T3, P00.S2.T2, P00.S3.T3 | AC57, AC69, WA-AC01 | Register: "P22.S1 Source intake (books)" IMPLEMENTED; "P00.S2.T2 Content responsibility" BLOCKED_EXTERNAL (B01: reviewers, rights) |
| OR02 | Future content is imported, reviewed and published through the admin panel (§1) | P06.S1–S4, P21.S3 | AC15, AC18, AC27 | "P06.S2.T1/T2 Structured import, preview and recovery" PARTIAL; "P06.S3.T2 Publish versioned content" IN_PROGRESS; "P06.S3.T3 Correction and retirement" IMPLEMENTED |
| OR03 | Punjab is the first active region; other provinces come later as content releases. Board and entrance mappings follow Punjab/exam sources (§1, §3, P00.S1.T1) | P05.S1–S4 | AC17, AC28 | "P05.S1 (curriculum model, catalogue)" IMPLEMENTED (structure); "P05.S3.T1-T3 Versioned exam profiles" IMPLEMENTED, no official profile entered (B02); "P05.S4.T2 Test future-region extensibility" IMPLEMENTED |
| OR04 | Classes 11 and 12 (P00.S1.T1) | P05.S1, P09.S1.T2 | AC02, AC05 | "P05.S1 (curriculum model, catalogue)"; SCOPE-01 keeps XI and XII separate |
| OR05 | For each topic: a video, an explanation and examples (§1; "videos" in P00.S1.T1) | P07.S1–S4, P11.S2.T1, P13.S2.T1, P22.S2.T1 | AC03, AC48, AC56 | "P11.S2.T1 / P13.S2.T1 / P07.S1.T1 / P07.S4 topic reader…" IMPLEMENTED (drafts only); book-draft rows "P07.S1 / W01.S1 Class XI/XII … book drafts" IMPLEMENTED (drafts only, not reviewed); "P07.S2.T1 Resumable/direct uploads" local archive only (B05); "P11.S2.T1 Lesson page" PARTIAL |
| OR06 | Every requested test mode: topic, chapter, selected chapters, half book, full book, combined Class 11 + 12 subject, and complete MDCAT/ECAT mocks (§1, §2.1, P00.S1.T1) | P09.S1.T1–T3, P09.S2.T1–T3, P09.S3, P10 | AC04, AC05, AC06, AC07, AC08 | "P09.S1.T1 Topic and chapter tests" IMPLEMENTED; "P09.S1.T2 Book and combined scopes" IMPLEMENTED; "P09.S2.T1/T2, P09.S3.T1-T3 Mocks from published profiles" PARTIAL (no verified profile, B02). Full official-pattern mocks are UNAVAILABLE where a profile needs sections outside SCOPE-01 (`LAUNCH_MANIFEST.md`) |
| OR07 | Results show weak concepts, why the answer was wrong and the next revision task (§1) | P12.S1–S3, P11.S3.T3 | AC16, AC46, AC52 | "P12.S1.T1 Versioned result summary" IMPLEMENTED; "P12.S3.T1-T3 Mistake notebook and spaced review" IMPLEMENTED |
| OR08 | Progress as three separate meters: syllabus coverage, completed content and demonstrated knowledge (§1, §6.1, §6.6) | P11.S1.T2, P12.S2.T1–T4 | AC52, AC61, AC62 | "P11.S1.T2 Personal dashboard and three meters" IMPLEMENTED; "P12.S2.T1/T2/T4 Evidence rules" IMPLEMENTED |
| OR09 | A written module in the same portal: chapter short and long questions, handwritten scan/PDF submission, rubric-based practice marks, an explanation of each mistake and a teacher recheck (§1, §20.1, P00.S1.T1) | W00–W08 (mainly W01, W03, W04, W06, W07) | WA-AC04, WA-AC16, WA-AC17, WA-AC24, WA-AC36, WA-AC57 | "W00.S1.T1 Freeze the student outcomes and exclusions" RECORDED (owner freeze pending, WA-D12); "W03.S1.T1 Browser capture/import" IMPLEMENTED (web); "W04.S2.T1–T3 Deadline-safe sealing" IMPLEMENTED; "W06.S2.T1 Learner rechecks" IMPLEMENTED |
| OR10 | An unreadable or pending answer is never marked zero. Pending and unavailable marks are shown separately (§1, §20.1) | W05.S1, W07.S1.T1, W02.S1.T3 | WA-AC06, WA-AC32, WA-AC62, WA-AC72, WA-AC86 | "W07 Completeness (scored/pending/unavailable)" IMPLEMENTED (teacher route); "W07.S1.T1 Marks presentation" IMPLEMENTED |
| OR11 | Every question has an approved rubric with alternate answers and partial-credit rules. In the R0 pilot a teacher verifies every result. Automatic marks are released only for independently qualified slices. Numericals and diagrams that are not supported get a funded teacher route or are shown as unavailable before the start (§20.1, §20.2.2–20.2.3) | W01.S2, W05, W06, W10.S1–S3 | WA-AC03, WA-AC31, WA-AC48, WA-AC49, WA-AC66, WA-AC67 | "W05 Automatic reading and rubric assessment" PARTIAL (disabled, B10); R0–R3 table in `RELEASE_CHECKLIST.md`; PILOT-R0-01 |
| OR12 | Chapter short and long answers are required core scope (R2). The R1 short-answer pilot is not the complete module, and R2/R3 claims must be precise (§20.1, §20.2.3, P00.S1.T1) | W00.S1.T1, W00.S3.T1, W10.S2, W11.S1 | WA-AC58, AC69 | "W00.S3.T1-T2 Release levels and policy defaults with owners" IMPLEMENTED as records; R0–R3 table in `RELEASE_CHECKLIST.md` |
| OR13 | A complete board mock with MCQ and written sections: each section keeps its own timing rules, the result is one versioned result, and this extended mode is qualified separately (§1, §20.7.4) | W04.S1.T4, W07.S1.T4, W10.S3.T4 | AC68, WA-AC91, WA-AC92 | Not registered (TODO); `RELEASE_CHECKLIST.md` R3 "Not started" |
| OR14 | Web, Android and iPhone use one account and one backend (§1, P00.S1.T1) | P04, P11, P13.S1–S4, P14.S3 | AC03, AC54 | "P13.S1 Native app shell" IN_PROGRESS; "P13.S2.T1 Mobile learning screens" PARTIAL; B07, B09, B14 |
| OR15 | A premium design whose essential learning and test flows still work on low-cost phones and weak internet, measured against device budgets (§1, §6, §6.2b) | P02, P11.S4, P13.S4, P20.S3 | AC26, AC49 | "P11.S4.T1 Route rendering and payload budgets" IMPLEMENTED (JS budget); "P02.S2.T1 Define tokens and typography" IMPLEMENTED; device budgets need B09 |
| OR16 | One 30-day platform trial with server-controlled expiry and supported repeat-device checks. A new email or phone, a cancellation or a reinstall does not intentionally reset it (§1, §16.1, P00.S1.T1) | P14.S5–S8, P04.S1.T1, P13 (attestation) | AC29–AC44, AC55, AC64–AC66, WA-AC54 | "P14.S5.T1/T2 One-time 30-day trial and ledger" PARTIAL; "P14.S5.T3 / P14.S6 Trial claims, device authorization, recovery" PARTIAL; per-scenario status in `TRIAL_ACCEPTANCE_MATRIX.md` |
| OR17 | Once the trial is used, show the trial-used or expired notice and paid subscription options. One offer covers web, Android, iOS and the advertised Punjab courses; switching course, exam or channel never creates a new offer (§16.1) | P14.S7.T3, P14.S1.T1 | AC30, AC42 | "P14.S7.T3 Truthful trial notices" IMPLEMENTED (web + mobile) |
| OR18 | Scale target of 5,000 simultaneously active students on a defined workload. It is not called verified until load-test evidence exists (§1, §6.2) | P17, P20 | AC24, AC50, AC63, WA-AC46 | "P20.S1.T2 Reproducible load scenarios" PARTIAL (B03) |
| OR19 | Anything that needs an owner or provider choice is recorded with a proposed default and is not a settled requirement (§1, §17) | P00.S1.T1, P00.S2.T3, W00.S3.T2 | AC60 | `DECISIONS.md` (section 17 note and WA-D register); group (c) below |

### Owner decisions recorded after the roadmap (from `DECISIONS.md`)

These refine group (a). They are listed here only so the trace is complete; the decisions themselves live in `DECISIONS.md`.

| Decision | Date | What it records | Refines |
|---|---|---|---|
| SCOPE-01 | 2026-10-06 | Approved academic scope: Punjab; Class XI and XII kept separate; Biology, Chemistry, Physics, Computer Science and Mathematics. English, Logical Reasoning, Statistics, compulsory board subjects and other provinces are outside the authorized scope | OR03, OR04, OR06 |
| D01 (interim) | 2026-10-06 | Launch manifest = SCOPE-01, every test mode for those subjects, and the required R2 written scope. G22 closes the final manifest | OR06, OR09, OR12 |
| AUTH-01 | 2026-10-06 | Standing implementation authorization. It does not cover new spending, contacting people, charging customers or public launch | P00.S1.T4 / D12 |
| Blocker scope rule (`BLOCKERS.md`) | 2026-10-07 | Missing reviewers or publication rights block only academic publication and qualification, never software | OR01 |
| TOPIC-READER-01 | 2026-10-16 | A topic opens one full lesson and drafts stay private. English is shown until a real Urdu or Roman Urdu variant exists | OR05 |
| BIO-XI-PILOT-01 | 2026-10-18 | The reader offers English / Roman Urdu, and each topic gets a Roman Urdu explanation written for it | OR05 |
| BIO-XII-START-01, CS-XII-BOOK-01 (authority and consequences) | 2026-10-19 | The owner excluded Mathematics XI and XII from book drafting | OR06; see open item 1 |
| CS-XII-P21-01 | 2026-10-21 | Printed page 21 of the Class XII Computer Science book is recorded as missing | OR01 |

## (b) Enhancements the roadmap added

The owner brief does not ask for these. The roadmap added them to make the owner requirements dependable or operable. Their task state is tracked the same way as group (a).

| ID | Enhancement (roadmap source) | Phases / tasks | Acceptance | Status pointer |
|---|---|---|---|---|
| EN01 | Three separately evidenced readiness states and the Representative Reviewed Content Set (§2.3, §2.4) | P00.S1.T2, P21, P22.S1.T3, P22.S2 | AC57, AC60, AC69 | "P00.S1.T2 Release boundaries" IMPLEMENTED; all three states NOT_READY in `RELEASE_CHECKLIST.md` |
| EN02 | An MCQ-only release must not be advertised as complete board-exam preparation (§2.1) | P22.S3.T3, W11.S1 | AC69 | No dedicated register row |
| EN03 | Content schema and renderer capability contract (§5.4) | P06.S3.T2, P13.S1.T4, P19.S3.T4 | AC47 | "P13.S1.T4 Client capability and supported-version policy" IMPLEMENTED (server) / CODE ONLY (mobile); "P19.S3.T4 …" IMPLEMENTED (API scenario) |
| EN04 | Configuration, app variants and the release manifest (§5.5) | P01.S1.T4, P03.S2.T3, P19.S4.T3, P23.S1.T3 | AC51, AC54 | "P03.S2.T3 Environment validation" IMPLEMENTED; "P19.S4.T3 Freeze a tested release candidate" PARTIAL |
| EN05 | An owned archive of media masters (§5.6) | P07.S2.T4, P17.S4.T1 | AC22, AC48 | "P07.S2.T4 Owned master archive and retention" IMPLEMENTED (local; B03, B05) |
| EN06 | Quarantine, correction and score-version propagation (§5.7) | P08.S4, P10.S3.T4, P12 | AC16, AC46, AC59 | "P08.S4.T1 Quarantine by defect type" IMPLEMENTED (MCQ); "P10.S3.T4 Reviewed MCQ corrections and regrades" IMPLEMENTED |
| EN07 | Locked-admission submission and deadline protocol, with five answer states (§10.5, §6.1) | P10.S1–S4, P11.S3.T2 | AC09–AC12, AC45, AC58 | "P10.S2.T1 Answer revisions and receipts", "P10.S3.T1 Atomic submission and expiry", "P10.S4.T1 Persistence failure cases" IMPLEMENTED |
| EN08 | Budgets for database connections, polling and background work (§5.8) | P01.S4.T4, P17.S2.T4, P20 | AC50, AC63 | "P01.S4.T4 Connection, recovery and background-work budgets" PARTIAL |
| EN09 | End-to-end budgets on student devices, requalification triggers and qualification records (§6.2b, §6.4, §6.5) | P02.S4.T1, P20.S3, P20.S4.T4 | AC49, AC51 | Named devices are B09; requalification item in `RELEASE_CHECKLIST.md` |
| EN10 | Versioned learning-evidence rules and honest comparisons with other learners (§6.6) | P12.S2 | AC52, AC61, AC62 | "P12.S2.T1/T2/T4 Evidence rules" IMPLEMENTED; "P12.S2.T3 Honest learner comparisons" IMPLEMENTED |
| EN11 | Wrong-answer notebook, spaced revision and time-budgeted study plans (§2.1, Improvement row) | P12.S3, P12.S4 | AC52 | "P12.S3.T1-T3 …" IMPLEMENTED; "P12.S4.T1 Time-budgeted study plan" IMPLEMENTED |
| EN12 | Multilingual search and its benchmark (P11.S2.T3/T4) | P11.S2.T3, P11.S2.T4 | AC53 | "P11.S2.T3 Content search" PARTIAL; benchmark needs B16 |
| EN13 | Storyboard studio and evaluated AI-assisted production (§2.1, Content production) | P07.S4.T1–T4, P22.S2.T4 | AC56 | "P07.S4.T1/T2 Storyboard records and prompt package" IMPLEMENTED; "P07.S4.T3 Review finished media" IMPLEMENTED as production records |
| EN14 | Launch manifest and measured production throughput (§10.4, P22.S2.T4) | P22.S1.T3, P22.S2.T4, P05.S2.T3 | AC57 | `LAUNCH_MANIFEST.md` (draft); P22.S2.T4 not registered |
| EN15 | Consolidated trial decisions: device limits, a bounded recovery window and conversion credit tied to its source (§16.4, §16.9, §16.10) | P14.S5.T4, P14.S7, P14.S4.T1 | AC38, AC55, AC64, AC65, AC66 | `TRIAL_ACCEPTANCE_MATRIX.md`; "P14.S5.T3 / P14.S6 …" PARTIAL |
| EN16 | Trial cohort economics and false-block reporting (§16.9 T7) | P14.S8.T4, P16.S2.T4 | none | "P16.S2.T4 Trial and paid cohort economics report" IMPLEMENTED (D13 BLOCKED_DECISION); "P14.S8.T4 …" IMPLEMENTED (report) |
| EN17 | Help centre, tickets, academic error reports and notifications (§2.1, Support row) | P15.S1–S4 | AC36 | "P15.S2.T1–T3 …", "P15.S3.T1 Help requests", "P15.S3.T3 Staff support queue and lookup" IMPLEMENTED |
| EN18 | Management dashboards and an audit trail (§2.1, Management row) | P16.S1–S4 | none | "P16.S1.T2 Academic overview", "P16.S4.T1 Audit explorer" IMPLEMENTED |
| EN19 | Controlled offline study packs (P13.S3) | P13.S3 | AC40 | "P13.S3.T1 Controlled study packs" IMPLEMENTED (API) / CODE ONLY (mobile) |
| EN20 | Accessibility to WCAG 2.2 AA, and right-to-left Urdu (§6.1) | P02.S4, P19.S2.T3 | AC26 | "P19 Accessibility (automated part)" PARTIAL |
| EN21 | Security and privacy verification (P18, P04.S4) | P18.S1–S4, P04.S4 | AC13, AC14, AC25, AC43 | "P18.S1.T2 Systematic authorisation" PARTIAL; "P18.S3.T2 Access and deletion requests" PARTIAL (B15) |
| EN22 | Backup and disaster-recovery targets (§6.2) | P17.S4 | AC22, AC23 | Needs B03 |
| EN23 | Written-module controls beyond the brief: a finite allowance ledger (§20.13.4), private evidence retention (§20.14), processor approval before any real script is sent (W00.S2.T4), admission limited by staffing (§20.13.3) and canary monitoring (W11.S2.T4) | W08, W00.S2.T4, W06.S3, W09, W11 | WA-AC39, WA-AC43, WA-AC59, WA-AC65, WA-AC69, WA-AC85 | "W08.S1.T2 Atomic allowance transitions" IMPLEMENTED; B10, B15 |
| EN24 | Bounded rubric-assessment AI as the only AI exception; the general tutor stays deferred (§2.2, §20.2) | W05, W08 | AC67, WA-AC28 | "W05 …" PARTIAL (disabled) |
| EN25 | Positioning hypothesis and a bounded validation plan (P00.S1.T4) | P00.S1.T4, P23.S3.T1 | none | `POSITIONING.md`; D12 |

**Deferred and therefore not first-release requirements (§2.2):** live classes, public forums, student-to-student messaging, teacher marketplaces, school multi-tenancy, biometric proctoring, admission or score prediction, a student-facing AI tutor, translated exam-question variants within one attempt, secure offline video downloads and other provinces. Under AC60 an optional deferred feature does not block unrelated work. The academic-doubt service is D11.

## (c) Owner decisions still open

### Section 17 (D01–D14)

Every row below shows the roadmap's **proposed default** (§17). A proposed default is not a decision. Under §7 it applies until the owner records otherwise. `DECISIONS.md` records D01 as interim and says D02–D14 remain at their proposed defaults, with nothing purchased, contracted or enrolled.

| ID | Decision | Proposed default (roadmap §17) | Record today | First affected gate |
|---|---|---|---|---|
| D01 | Launch manifest scope: tracks, subjects, languages, years, modes | All owner-requested modes for the supplied subjects, plus required R2 chapter short/long written scope; RCS first; enabled full board mocks need R3 | D01 (interim) 2026-10-06; final at G22. See open items 1 and 2 | G00 draft, G22 final |
| D02 | Pricing, bundles, renewal | Fixed-duration one-time purchases on the web; store subscriptions only if D04 adopts them; prices configurable | Proposed default; no products or prices (PRODUCTS-01, PRICING-01); B06 | G14 |
| D03 | Web payment provider | One provider behind the adapter after an eligibility check | Proposed default; B06 | P14.S2.T1 |
| D04 | Native billing at launch | Store billing for in-app digital purchases; no external purchase links | Proposed default; B07 | G14 |
| D05 | Invalid-item treatment in official-pattern mocks | EXCLUDE; a valid item with a wrong key uses reviewed KEY_CORRECTION | Proposed default | G08, G10 |
| D06 | Pool-sufficiency rule | At least 3 approved unique families per blueprint slot | Proposed default (quoted in `LAUNCH_MANIFEST.md`) | G08, G22 |
| D07 | Trial device limits | 3 devices; 1 self-service replacement per 7 days | Proposed default; used by the code (TRIAL-02) | G14 |
| D08 | Minimum supported OS versions | Android 9+, plus an iOS floor chosen with the pinned stable SDK and field/device evidence | Proposed default; needs B09 | G13 |
| D09 | Early paid-conversion credit | Unused whole trial days added once to a qualifying web fixed-term purchase; none for store subscriptions | Proposed default; B06 | G14 |
| D10 | Android device recall enrolment; developer-account stability | Submit the beta interest form at M1; keep the Apple team and Google developer account stable | Proposed default; B08 | P01.S4.T1, P14.S6 |
| D11 | Academic doubt service | Not in the first release; pilot after launch if adopted | Proposed default | Outside first-release gates |
| D12 | Market validation experiments | Plan recorded (P00.S1.T4); no contact or spending without authorisation | Plan in `POSITIONING.md`; not authorised, not run | Before acquisition spend |
| D13 | Trial cohort budget and rollout limits | Cohort economics report approved before funded acquisition | "P16.S2.T4 …" BLOCKED_DECISION (D13) | G23 |
| D14 | Cloud region, PostgreSQL major version, managed plans | Region chosen by measured Punjab latency; managed versions and plans from measured load | Proposed default; PostgreSQL 17 locally (`STACK.md`); B03 | P17.S1 |

The consolidated trial decisions in §16.9 also carry proposed defaults. T4, T5 and T6 are D07, D09 and D10 above. The code applies T1 (stable program identity, IMPL-22) and, through TRIAL-02, T2 (a web grant does not unlock a consumed native device), T3 (7-day recovery window, then review) and T8 (no trial after paid history) as planning defaults. T7's owner, the student operations lead, has not been named (P14.S8.T1).

### Section 20.19 (WA-D01–WA-D15)

The roadmap starts every row as PROPOSED / NOT YET APPROVED. `DECISIONS.md` records "Not recorded" as the approval for all fifteen and lists the provisional interim default the code uses for each.

| ID | Decision | Recommended starting position (roadmap §20.19, shortened) | Owner / deadline |
|---|---|---|---|
| WA-D01 | First subject, grade, chapter and language | One well-supported XI conceptual short-answer slice from owner data | Owner + academic lead / WG00 |
| WA-D02 | Rubric authority and reviewer team | Official schemes where available; otherwise teacher-reviewed practice rubrics with independent approval | Academic lead / WG01 |
| WA-D03 | Writing, upload and optional-answer policy | Separate D/G/U; proposed 10/20-minute allowances only after byte and uplink qualification | Academic + product / WG04 |
| WA-D04 | Input formats and page limits | Qualified JPEG/PNG/PDF and the §20.8 caps | Mobile/web/security / WG03 |
| WA-D05 | Model/OCR route and terms | Benchmark permitted candidates on real scripts; pin versions or keep teacher review | Applied AI + privacy / WG05, WG08 |
| WA-D06 | Statistical release policy | Freeze severe-error definitions, thresholds and the 200/60/20 minimum before the held-out set is used | Evaluation + academic / WG10 |
| WA-D07 | Trial and paid allowance and rates | Cost-backed weighted units, remedies, no new trial | Owner + commerce / WG08 |
| WA-D08 | Review staffing and service | Fund real coverage; subtract fixed and backlog work before admitting new work | Academic operations / WG06, WG09 |
| WA-D09 | Rescan, appeal and remedy windows | 14-day recheck, 7-day action and remedy, three-way rescan classification | Academic + product / WG06, WG08 |
| WA-D10 | Evidence and score retention and deletion | 90-day scans and readings, 12-month feedback, bounded appeal holds | Privacy/legal + owner / WG08 |
| WA-D11 | Urdu, numericals and diagrams | Qualify each slice independently or keep it unavailable | Academic + product / WG10 |
| WA-D12 | Release scope and load promise | R2 chapter short and long scope for the default complete product | Owner + platform/academic / WG11 |
| WA-D13 | Progressive upload and capture policy | Upload from the start; a measured 2,000–3,000-pixel preset with a higher-detail fallback | Product + mobile/web / WG03 |
| WA-D14 | Provider processing location and terms | Approve each candidate before any real-script call | Privacy/legal + owner / before W02.S3 real calls |
| WA-D15 | Composite board-paper policy | Only source-verified parent/child timing, choices, maxima, corrections and release | Academic + product/assessment / before R3 |

## Open items found while tracing

None of these is decided here. Each needs the owner.

1. **Mathematics.** SCOPE-01, D01 (interim) and `LAUNCH_MANIFEST.md` list Mathematics as an active subject. On 2026-10-19 the owner excluded Mathematics XI and XII from book drafting (BIO-XII-START-01, CS-XII-BOOK-01). Under §10.4, reducing the promised scope needs an explicit owner decision (D01), and none is recorded. The Pre-Engineering track (Math/Chem/Phy) and the in-scope ICS combination (CS/Math/Phy, DISCOVERY-01) both depend on Mathematics.
2. **Explanation languages.** `LAUNCH_MANIFEST.md` (2026-10-06) still says Urdu and Roman Urdu are UNDECIDED. Since then the owner briefs (TOPIC-READER-01, BIO-XI-PILOT-01) have directed English and Roman Urdu lessons, and every drafted book follows that. Roadmap §6.1 also lists Urdu as a supported variant. The launch-manifest field belongs to D01.
3. **"Subscription."** §16.1 and ACCESS-02 describe a trial followed by a subscription. The D02 default is fixed-duration one-time web purchases. Whether "subscription" means recurring billing is part of D02.
4. **Purchaser.** P00.S1.T3 includes a purchaser who may differ from the learner. §4 defines no such role (see `LEARNERS_AND_JOURNEYS.md`).
5. **Register row.** "P00.S1.T1 Owner requirements" is IN_PROGRESS and names this trace table as what remains. This file is that table. Updating the register is left to whoever integrates the records.
