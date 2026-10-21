# POSITIONING (P00.S1.T4)

Roadmap task **P00.S1.T4, "Record the positioning hypothesis and bounded validation plan"** (roadmap §8, P00.S1; decision D12). Written 2026-10-21. This file records the hypothesis as the roadmap states it, the competitor statements the roadmap contains, and a validation plan. It is a record, not an approval. The hypothesis has not been tested. The plan is **proposed, not run**: running it needs the owner and real learners. No web research was done for this file, and no person was contacted.

## The hypothesis (roadmap P00.S1.T4)

> Punjab-focused preparation with verified syllabus/year mapping, understandable multilingual explanations, recoverable tests and a practical daily plan that works on the learner's actual phone and network.

It is a hypothesis about what learners value. Nothing in the repository is evidence that it is true.

### What the hypothesis relies on, and where each part stands

This table shows whether the product can deliver each part. It is not evidence that learners want it.

| Part of the hypothesis | Product capability (roadmap) | State today (records) |
|---|---|---|
| Punjab-focused, with verified syllabus/year mapping | Separate board and entrance inclusion records; exam profiles verified per year (§3, P05.S2, P05.S3) | Engineering exists ("P05.S2.T1–T3 …", "P05.S3.T1-T3 Versioned exam profiles" IMPLEMENTED). No official profile has been verified (B02), and real mappings need reviewers (B01) |
| Understandable multilingual explanations | Separately versioned English, Urdu and Roman Urdu variants (§6.1, P07.S1.T2) | English and Roman Urdu drafts exist for every topic of Biology, Chemistry, Physics and Computer Science, Classes XI and XII (the BIO/CHEM/PHY/CS book decisions). None is reviewed (B01), and no Urdu-script lessons are drafted |
| Recoverable tests | Durable saves, five answer states, locked-admission submission (§6.1, §10.5, P10) | "P10.S2.T1", "P10.S3.T1" and "P10.S4.T1" IMPLEMENTED; web e2e in `practice.spec.ts`; no device evidence (B09, B14) |
| A practical daily plan | Time-budgeted study plan (P12.S4.T1) | "P12.S4.T1 Time-budgeted study plan" IMPLEMENTED. Exam-weight priority needs verified profile weights (B02; STUDYPLAN-01) |
| Works on the learner's actual phone and network | Device budgets and network profiles (§6.2b) | Proposed targets only. No named reference devices (B09) and nothing measured |

Two things are not in the roadmap's hypothesis: the handwritten written-answer module (§20) and the 30-day trial (§16). Whether they belong in the positioning is an open question for the owner. D11 lists "differentiation" as an impact of the academic-doubt service, which is also outside the first release.

## Competitor statements

The roadmap's reference register (§14) contains three competitor entries. §14 says they were checked on 5 October 2026 and that "Competitor pages support only what those vendors advertise." They are reproduced here as the roadmap gives them. Each is a **vendor claim, unverified**: not measured, and not rechecked since 5 October 2026.

| Roadmap ref | Vendor | Advertised features as recorded in roadmap §14 | Status |
|---|---|---|---|
| S37 | Maqsad | Daily live classes, recorded lectures, 15,000+ MCQs per exam, weekly mock tests, instant doubt-solving, 1:1 tutoring, free demo class | Vendor claim, unverified |
| S38 | Nearpeer MDCAT | 30,000+ questions, mistakes diary, score predictor, analytics, live lectures, AI bot, daily schedule, free to start with usage limits | Vendor claim, unverified |
| S39 | TopGrade | Personalised schedule, adaptive road map, chapter/quarter/half/full syllabus tests, daily mentor hours, money-back guarantee | Vendor claim, unverified |

No other competitor claims have been collected. Several of these advertised features are things the roadmap defers for the first release (§2.2: live classes, score or admission prediction, a student AI tutor), so they are not in this product's scope.

## Validation plan: proposed, not run

**Authority.** D12's proposed default is "Plan recorded (P00.S1.T4); no contact or spend without authorisation". AUTH-01 does not cover contacting people or new spending, and roadmap §11 rule 13 forbids contacting learners for research without owner authorisation. Under P00.S1.T4 this plan is not a release gate. P23.S3.T1 says to run the D12 experiments "if authorised".

The roadmap fixes who to interview, the willingness-to-pay check and the single channel test. **Numbers, durations and decision thresholds below are this record's proposal, not roadmap figures.** The owner may change any of them.

### Who and how many

| Group (P00.S1.T4 / P00.S1.T3) | Proposed number |
|---|---|
| Medical (Pre-Medical, MDCAT) learners, Class XI and XII | 5 |
| Engineering and ICS (ECAT) learners | 5 |
| Repeat entry-test candidates | 5 |
| Purchasers who are not the learner (for example parents) | up to 5 |

That is 15 learners plus up to 5 purchasers, about the same scale as the roadmap's other small studies: at least five learners for prototype tests (P02.S4.T3) and roughly 15–30 invited students for UAT (P19.S4.T1). The results are qualitative. A sample this small can't establish market size, and it shouldn't be quoted as a percentage of learners.

### How (proposed)

- One short semi-structured interview per person, about 30 minutes, in the language the participant prefers (English, Urdu or Roman Urdu).
- Recruitment goes through a channel the owner authorises. Consent comes first. If a participant is a minor, guardian consent follows the legal/product review that P04.S4.T1 requires. Nothing is recorded without consent.
- Unreviewed draft lessons are not shown to participants (OR01, TOPIC-READER-01: drafts stay private). The interview is about how people study now.
- Notes are kept without names. Because the repository is public (IMPL-01), no personal data goes into it. Only an anonymised summary is recorded in `DECISIONS.md` under D12.

### Questions (proposed; neutral wording, mapped to the hypothesis)

1. How do you prepare for your board exams and for MDCAT or ECAT now? Which books, academies, apps or videos do you use? *(baseline)*
2. Has a resource ever covered the wrong syllabus, edition or exam year for you? What happened? *(verified mapping)*
3. Which language do you understand explanations best in: English, Urdu script or Roman Urdu? Does that change between subjects? *(multilingual explanations; D01 languages)*
4. Tell me about a time a test or app lost your answers, or your internet dropped during a test. *(recoverable tests)*
5. How do you decide what to study each day? Do you follow any plan? *(daily plan)*
6. Which phone do you study on, how much storage is free, and what is your internet like at home and at your academy? *(device and network; §6.2b, D08)*
7. Do you practise writing long answers by hand? Who checks them now, and how long does that take? *(written module; outside the roadmap hypothesis)*
8. What do you pay now for academies, tutors or apps, and who pays? What does that money buy that matters most: teacher contact, tests, notes or something else? *(willingness to pay against perceived teacher support, P00.S1.T4)*
9. Would you start a 30-day free trial that asks for no payment details? What would make you keep paying afterwards? *(trial and conversion; §16.1, D02)*
10. (Purchasers) What would you want to see or control when paying for a learner's preparation? *(purchaser; §13.2 parent dashboard is deferred)*
11. (Repeat candidates) What did you lack the first time that you need now? *(repeat-candidate needs)*

### The one bounded channel test (P00.S1.T4)

This needs spending, so it needs the owner's explicit authorisation (D12) and a budget cap from the owner (related to D13). It also needs a deployed public site, which waits on B03. The proposal: one channel, a fixed budget and a fixed duration, all set by the owner. The test measures visits, sign-ups and trial starts with the existing funnel report (register "P16.S2.T2 Funnel and retention"). No price, coverage or capacity claim may be made that the records don't support (§13.1; `RELEASE_CHECKLIST.md`).

### What result would change the plan (proposed decision rules)

These rules decide which question to take to the owner. None of them changes scope by itself.

| If, in a group, about 3 or more of 5 participants… | Then raise with the owner |
|---|---|
| don't see syllabus or year mismatch as a problem with what they use now | Don't lead the positioning with "verified mapping"; keep it as a quality rule |
| prefer Urdu script, or English only, over Roman Urdu | Language priorities for lesson production and review (D01 explanation-language field) |
| are ICS or Pre-Engineering learners and name Mathematics as essential | The Mathematics exclusion (`REQUIREMENTS_TRACE.md`, open item 1; D01) |
| are repeat candidates who mainly want full official-pattern mocks | Full mocks depend on B02, and on English and Logical Reasoning, which are outside SCOPE-01 (D01) |
| tie willingness to pay mainly to teacher contact | Whether the written teacher-review route (WA-D08) or the doubt service (D11) belongs in the offer; pricing (D02) |
| say a parent decides and pays, and wants visibility | A purchaser model and the deferred parent dashboard (§13.2); guardian consent (P04.S4.T1) |
| study on phones or networks worse than the §6.2b lab profiles | Choice of reference devices (P02.S4.T1, B09) and the minimum OS (D08) |

If no group shows a clear pattern, the hypothesis stays as written and the plan goes on unchanged. That result is recorded too.

## Open questions for the owner

1. Authorise the interviews, the channel and a budget cap (D12, D13), or record that validation is deferred.
2. Should the written module and the 30-day trial be part of the positioning statement?
3. The purchaser group needs a definition before purchasers can be interviewed (`LEARNERS_AND_JOURNEYS.md`).
