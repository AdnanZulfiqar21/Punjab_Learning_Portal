# OPERATING ASSUMPTIONS (P00.S2.T3)

Roadmap task **P00.S2.T3, "Define product operating assumptions"** (roadmap §8, P00.S2). Written 2026-10-21. The task asks for age range, launch courses, language variants, the free/paid model and support availability to be recorded as proposed settings, with pricing, retention periods and store distribution kept configurable until the owner settles them (§17). This file is a record, not an approval. Each row gives the proposed setting, its source and the decision that would confirm it. Where the roadmap and records give nothing, the row says so and leaves the question open. A setting changes only through `DECISIONS.md`.

**State values:** *Settled* means an owner decision is recorded in `DECISIONS.md`. *Proposed default* means a roadmap default that applies until the owner records otherwise (§7). *Open* means there is no source and nothing is proposed.

## Age range

| Assumption | Proposed setting | Source | Confirming decision | State |
|---|---|---|---|---|
| Learner age range | **None recorded.** The roadmap gives no age range. It describes learners by class (XI/XII) and entry-test route (header, §1, P00.S1.T3) | P00.S1.T3, §3 | Owner, with the legal/product review in P04.S4.T1. Not a §17 decision | Open |
| Age data and defaults | Collect the minimum age information needed; profiles are private by default | P04.S4.T1 | Same review; privacy schedule B15 | Proposed (roadmap task text) |
| Guardian consent | The requirement for the actual operating jurisdiction needs legal/product review. Age and guardian handling must be approved before any real script goes to a provider | P04.S4.T1, P18.S3.T3, §20.14 | Owner + legal (B15; WA-D10, WA-D14) | Open |
| Store age rating | Prepared at store submission for the production variant | P23.S1.T2 | Owner (B07) | Open |

## Launch courses

| Assumption | Proposed setting | Source | Confirming decision | State |
|---|---|---|---|---|
| Region and board | Punjab, Pakistan. Board identifiers are imported from an approved source, never hard-coded | §3, SCOPE-01, `LAUNCH_MANIFEST.md` | SCOPE-01 | Settled (owner, 2026-10-06) |
| Classes | Class XI and Class XII, kept separate in every record | SCOPE-01 | SCOPE-01 | Settled (owner, 2026-10-06) |
| Subjects at launch | **Biology, Chemistry, Physics and Computer Science, for Class XI and Class XII.** Mathematics XI and XII is excluded by the owner for now | SCOPE-01 lists five subjects including Mathematics. The owner instruction of 2026-10-19 ("no Mathematics XI or XII", recorded in BIO-XII-START-01 and CS-XII-BOOK-01) excludes Mathematics | D01. Under §10.4, narrowing the promised scope needs an explicit owner decision, and none records the Mathematics change in the launch manifest. `LAUNCH_MANIFEST.md` still lists Mathematics as active | Proposed; conflict open |
| Outside scope | English, Logical Reasoning, Statistics, compulsory board subjects, other provinces | SCOPE-01 | SCOPE-01 | Settled (owner, 2026-10-06) |
| Tracks | Pre-Medical (Bio/Chem/Phy) is complete within the proposed subjects. Pre-Engineering (Math/Chem/Phy) and the provisional ICS combination (CS/Math/Phy) have no Mathematics content while it is excluded | `LAUNCH_MANIFEST.md`, DISCOVERY-01 | D01 | Open (depends on the Mathematics decision) |
| Exam profiles | MDCAT and ECAT section practice for in-scope subjects. A full official-pattern mock is unavailable where the verified profile needs sections outside scope (MDCAT English and Logical Reasoning; ECAT English; ECAT combinations with Statistics). Four of ECAT's five intermediate combinations include Mathematics (§3). No profile is published until two reviewers verify it | §3, SCOPE-01, `LAUNCH_MANIFEST.md` | D01; B02 | Proposed; blocked on B02 |
| Test modes | Every subject and class: topic, chapter, selected chapters, half book, full XI, full XII, combined XI+XII. Pool rule: at least 3 approved unique families per blueprint slot | §10.4, `LAUNCH_MANIFEST.md` | D01; D06 | D01 interim; D06 proposed default |
| Written scope | Required R2 chapter short and long answers for the complete-product claim. Deployed roles run the R0 teacher-reviewed pilot | D01 (interim), WRITTEN-SCOPE-01, PILOT-R0-01 | WA-D12 (no approval recorded) | Proposed default |

## Languages

| Assumption | Proposed setting | Source | Confirming decision | State |
|---|---|---|---|---|
| Lesson explanation languages | **English (the book language) and Roman Urdu**, one variant of each per topic. Hard Urdu words get the English word on first use. Urdu-script variants are supported by the model, but none is drafted | §6.1 (English, Urdu and Roman Urdu as versioned variants); owner briefs TOPIC-READER-01 (2026-10-16) and BIO-XI-PILOT-01 (2026-10-18); the BIO/CHEM/PHY/CS book decisions; LESSON-VARIANTS-01 | D01 (the launch manifest's explanation-language field). `LAUNCH_MANIFEST.md` still says "UNDECIDED" (2026-10-06) | Proposed; manifest field open |
| Language of test questions | One language variant is fixed per attempt. Translated question variants within one attempt are deferred | §5.4 rule 7, §2.2 | D01 | Proposed (roadmap rule) |
| Written answer language | English text answers only today. Urdu answer scripts are a separate capability that must be qualified. Roman Urdu feedback is optional after terminology review and is not an accepted board answer language | §20.2.2; WA-D11 interim default (`DECISIONS.md`) | WA-D11 (no approval recorded) | Proposed default |
| Help and notices | Help articles exist in `en` and `ur` locales. Trial notices need reviewed Urdu and Roman Urdu equivalents. The video and text language controls are separate from the interface language | HELP-01, §16.5, P02.S3.T1 | D01 | Proposed |

## Free/paid model and trial

| Assumption | Proposed setting | Source | Confirming decision | State |
|---|---|---|---|---|
| Free access | The catalogue, chapter outlines and any lesson a publisher marks as a free preview. Lessons are premium unless marked; no previews are chosen yet, apart from development fixtures | P14.S1.T1, ACCESS-02 | D02 (which lessons are previews) | Proposed default |
| Trial | One 30-day platform trial (`PLATFORM_TRIAL_30D`). It starts when the learner selects "Start free trial", ends exactly 30 × 24 hours after the grant commits, needs no payment details and doesn't auto-charge. It covers web, Android, iOS and the advertised courses. It never restarts per course, exam, channel or terms revision, and a refund doesn't restore it. There is no separate written-module trial | §16.1, §16.9 T1/T8, §20.13.4; IMPL-22, TRIAL-02 | The trial requirement is the owner's (§16.1). Before launch, §16.8 asks the owner to confirm the trial scope, the non-autocharging billing default, D07, D09, support ownership and evidence retention | Requirement settled; billing default proposed |
| Trial devices | Up to 3 registered devices; 1 self-service replacement per 7 days | §16.9 T4; TRIAL-02 | D07 | Proposed default |
| Paid plans | Fixed-duration one-time purchases on the web. Products are the platform, a subject package, an exam package or a bundle, each lasting 1 to 366 days, sold on the web channel only. No products, prices or checkout exist yet | D02 default; PRODUCTS-01, PRICING-01 | D02, D03 (provider, B06) | Proposed default |
| Native purchases | Store billing for in-app digital purchases, with no external purchase links | D04 default; P14.S3.T1 | D04 (B07) | Proposed default |
| Early conversion | Unused whole trial days are added once to a qualifying web fixed-term purchase. Store subscriptions get none | §16.10; D09 default | D09 | Proposed default |
| Written marking allowance | Trial: 10 units (short answer 1, long answer 2), and at most 2 unsealed written permits. The amounts wait on measured cost. While the R0 pilot runs in deployed roles, written tests are open only to staff-granted pilot entitlements | ACCESS-01, §20.13.4, PILOT-R0-01 | WA-D07, WA-D12 | Proposed default |

## Support availability

| Assumption | Proposed setting | Source | Confirming decision | State |
|---|---|---|---|---|
| Support hours and response times | **None recorded.** The roadmap sets no support hours. Public Launch Ready needs "staffed support" (§2.3, `RELEASE_CHECKLIST.md`), and the controlled rollout needs "real support coverage" (P23.S2.T1) | §2.3, P23.S2.T1 | Owner (§12.2: operating business) | Open |
| Support channels | Help centre, help requests with screenshots, academic error reports and a staff lookup with a redacted timeline, all built | P15; register rows "P15.S2.T1–T3", "P15.S3.T1", "P15.S3.T3" IMPLEMENTED | None needed for the software | Built (not staffed) |
| Trial appeals and shared devices | Owned by the student operations lead, who is not yet named | §16.7, P14.S8.T1, §16.9 T7 | Owner (names the lead) | Open |
| Written review turnaround | Proposed staffed targets: 90% of review cases resolved within 24 hours and 99% within 48 hours, if advertised in calendar time. These apply to written review cases, not general support | §20.10 | WA-D08 (no approval recorded) | Proposed default |
| Time zone for dates and schedules | Stored in UTC; shown in Pakistan time (Asia/Karachi) by default | P15.S1.T3, DAYS-01 | None needed | Implemented |

## Devices and browsers

| Assumption | Proposed setting | Source | Confirming decision | State |
|---|---|---|---|---|
| Web browsers | See `SUPPORTED_BROWSERS.md`. Chromium browsers: current and previous two majors. Firefox: current and ESR. Safari 17+ and iOS 17+. Old browsers get server-rendered pages, but interactive features aren't promised there | BROWSERS-01, P19.S2.T1 | Owner review of the range against real learner traffic (BROWSERS-01) | Initial engineering policy |
| Native minimum OS | Android 9+, plus an iOS floor chosen with the pinned stable SDK (Expo SDK 57, `STACK.md`) and field/device evidence. Not verified | D08 default, §5.0 | D08 (owner + engineering; G13), needs B09 | Proposed default |
| Reference devices | At least one 2–3 GB RAM Android phone running Android 10–12, one current budget Android phone and the oldest supported iPhone. Exact models are chosen in P02.S4.T1 | §6.2b | Owner procurement (B09) | Open |
| Network profiles for budgets | Healthy: 4/1 Mbps, 150 ms. Degraded: 1/0.5 Mbps, 300 ms, 1% loss. These are lab profiles, not claims about Punjab coverage | §6.2b | None (engineering targets) | Proposed targets |

## Kept configurable until the owner settles them (P00.S2.T3, second bullet)

| Setting | Current handling | Decision |
|---|---|---|
| Pricing and bundles | Product and price model built; finance enters prices, with two people required to publish terms; nothing is priced | D02 |
| Retention periods | Proposed: raw scans and readings 90 days, feedback 12 months, bounded appeal holds. Today nothing is erased automatically, and deletion requests go to support | §20.14, WA-D10, PRIVACY-01; B15 |
| Store distribution | No store accounts; billing products aren't configured | D04; B07 |

## Open questions for the owner

1. **Mathematics:** record whether Mathematics XI/XII leaves the launch manifest (D01). This decides the Pre-Engineering and ICS tracks and four of the five ECAT combinations.
2. **Languages:** confirm English plus Roman Urdu as the launch explanation languages, and whether Urdu-script lessons are planned (D01 manifest field).
3. **Age range and guardian consent:** set the expected age range and commission the P04.S4.T1 legal/product review (with B15).
4. **Support hours:** set support hours and response targets, and name the student operations lead (P14.S8.T1).
5. **Paid model:** confirm whether "subscription" (§16.1) means recurring billing or the D02 fixed-duration purchase, and set prices and free previews (D02).
