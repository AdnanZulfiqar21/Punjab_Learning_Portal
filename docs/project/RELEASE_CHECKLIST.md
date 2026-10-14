# RELEASE CHECKLIST

Three separately evidenced states (roadmap §2.3). Nothing is ticked without current evidence. A blocker note is not evidence.

## Platform Ready (on the RCS): NOT_READY
- [ ] P00–P21 mandatory scope VERIFIED; G00–G20 PASSED for their recorded scopes
- [ ] RCS published and reviewed (§2.4): one complete chapter per subject with lessons, video+captions, question families; selected-chapters/half/full XI/full XII/combined forms for ≥1 subject; one reviewed mock per launch profile (unavailable profiles documented under SCOPE-01)
- [ ] Written R2: approved short+long questions/rubrics, teacher route qualified/funded per advertised chapter scope; WG11[PRELAUNCH, RCS]
- [ ] Web, Android, iOS (installable production variants) and admin operate on the RCS
- [ ] Zero unresolved P0/P1 defects
- [ ] Advisory review (`docs/security/advisory-review.md`) re-run on the release candidate's lockfiles within 7 days of release; every open finding has an owner, reason and target date (ADVISORY-REVIEW-01)

## Content Ready: NOT_READY
- [ ] Full launch manifest reviewed, licensed (rights confirmed), mapped and published (G22)
- [ ] Written questions/rubrics and assessment routes for every advertised scope

## Public Launch Ready: NOT_READY
- [ ] Exact release manifest, live providers (identity, media, payments, stores), staffed support
  - The manifest (`python -m portal_api.release manifest`, RELEASE-CANDIDATE-01) must be produced against the deployment database so `content_release_id` and `runtime_overrides` are not null, with image digests (B03) and the native build's OTA runtime (B07) filled in.
- [ ] Store decisions, P23/W11 staged live evidence, owner launch authorization
- [ ] Production web sets `PORTAL_PUBLIC_ORIGIN`; `robots.txt` and `sitemap.xml` checked on the live host (PUBLIC-SITE-01)

## Release stop conditions (§13.1)
Incorrect grading · lost acknowledged answers · submission-protocol violations · exposed keys/private data · unreliable payment access · failed recovery · open P0/P1 · unreviewed advertised content · manifest drift · unsupported capacity claims · (written) missing rubrics/permissions, unqualified automatic slices, overwritten human decisions, misleading pending totals, double-consumed allowances, unapproved processors.


## Written-assessment release levels R0-R3 (W00.S3.T1; written 2026-10-12)

Each level lists its gate and what exists today. A level is reached only with its evidence, never by this table.

| Level | What it allows (§20.15) | Built so far (engineering) | Still needed before the level can be claimed |
|---|---|---|---|
| R0 controlled teacher-reviewed pilot | Accepted real scripts, provider approval, safe flows, every released mark verified by a teacher, tracked non-billable pilot allowance | Teacher marking with leases, rechecks, rescans and adjudication; every release is a teacher decision; pilot entitlements and the allowance ledger | Real scripts and consent (B10); named teachers (B01). The R0 pilot switch exists and is on by default in deployed roles (PILOT-R0-01). |
| R1 qualified short-answer practice | Frozen evaluation and routing policy, passing short-answer slices, capacity and client gates | Assessor contract, validation, provenance and failure handling with a fixture (AUTOASSESS-01, AUTO-RECOVERY-01, AUTO-PROVENANCE-01); calibration subsets | A qualified provider and passing slices (B10, WA-D06); client device evidence (B14) |
| R2 required core written module | Short and long chapter practice for the approved scope, qualified automatic capabilities as promised plus funded review escalation, all clients, operations evidence | Short and long questions, subparts, rubrics, web and mobile capture, results, history, rechecks, staffing and admission | Approved content and rubrics (B01); qualification (B10); devices (B09, B14); production operations (B03) |
| R3 extended types and board forms | Numerical and diagram qualification, composite board forms, full-form capacity | Not started (W04.S1.T4, W07.S1.T4) | WA-D15, verified board patterns (B02), qualification (B10) |
