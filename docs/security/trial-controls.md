# Free-trial operational and privacy controls (P14.S8.T2, TRIAL-CONTROLS-01)

**Written:** 2026-10-12. This covers how the one-free-trial rule is run and what it may keep about a person or a device. It sits alongside `docs/security/data-minimisation.md` (what is collected) and `docs/project/TRIAL_ACCEPTANCE_MATRIX.md` (what has been tested).

Two things are still outside this document:
- the approved retention schedule (B15);
- the real device providers (Apple DeviceCheck/App Attest and Google Play Integrity device recall; B07, B08).

Until those exist, the device adapters report "provider not configured" and never invent a verdict.

## What is kept, and for how long

| Record | Kept | Never kept |
| --- | --- | --- |
| Trial grant | Account, program, start and end, status | — |
| Trial claim | Surface (web, iOS, Android), a peppered SHA-256 **reference** for the app install, the adapter's verdict and detail, the marker-write outcome, state history | The install token itself, hardware identifiers, advertising IDs, phone number, IP address, raw attestation tokens |
| Device use | The same install reference, a label the person chose, method, dates | As above |
| Exception | Who it is for, surface, the reviewer, the reason, expiry | — |

`tests/test_trial_controls.py` fails if a trial table gains a column for a hardware identifier, an advertising ID, a phone number, an IP address or a raw token. It also fails if anything a client sends in its device proof is stored beyond the verdict.

**Retention:** nothing is erased automatically yet. Deletion requests are recorded and routed to support (PRIVACY-01). How long trial evidence is kept after a deletion request, and what must be kept to stop repeat trials, is part of the approved retention schedule (**B15**). No permanent matching promise is made to learners.

## What learners are told, before they start

The trial offer says the following, on the web (`components/plan-status.tsx`) and in the app (`components/plan-card.tsx`):
- there is one free trial per person;
- the apps **may** check whether a phone has already had a free trial;
- only a random reference for the app on that phone is kept, never the phone's identity;
- shared or second-hand phones can ask for help, and a person reviews them.

The word "may" is deliberate: without B07/B08 the check is the account rule only.

## Who can do what (least privilege)

| Who | Can | Cannot |
| --- | --- | --- |
| The learner | See and remove their own trial devices; ask for help | See anything about another account |
| Support, with `review_trial_eligibility` and MFA | See a redacted timeline that includes trial decisions; grant a **bounded** exception with a reason (audited, expires, account-scoped) | Clear or change a provider marker; see install tokens; extend a trial |
| Finance and the owner, with MFA | See the weekly trial-decision report (TRIAL-QUALITY-01) and the cohort economics report | Change claims or exceptions |
| Everyone else | — | Any of the above (`tests/test_authorization_matrix.py`) |

An exception never clears a provider marker or the trial history. It applies to that account and surface until it expires: the device limit still applies, and each use is recorded on the exception.

## Provider markers (proposed allocation, B07/B08)

The allocation below is **proposed**. Recheck the bit counts against each provider's documentation when the adapters are integrated.

| Provider | Storage per device | Allocation |
| --- | --- | --- |
| Apple DeviceCheck | 2 bits per device per developer team | Bit 0: `PLATFORM_TRIAL_30D` consumed. Bit 1: reserved. |
| Google Play Integrity device recall | A few bits per device per app | Bit 0: `PLATFORM_TRIAL_30D` consumed. The rest: reserved. |

- A reserved bit is never repurposed without a new, recorded program decision.
- A new trial program needs its own bit.

**Decision D10, recorded for the owner:** the markers belong to the Apple developer team and the Google Play developer account that publish the apps. If the apps move to another team or account, the markers stay behind. Devices then look new, and repeat trials become possible until the account history catches them. Moving the apps is therefore a trial-policy decision, not only a publishing one.

## Monitoring

**The weekly trial-decision report** (`/admin/trial-decisions`, TRIAL-QUALITY-01) shows, per cohort:
- claims;
- unknown verdicts;
- denials;
- appeals;
- overturned denials, the false-block proxy, with a target under 2 %;
- claims still in review.

The student operations lead owns appeals and the monthly false-block review. **The owner hasn't named one yet (P14.S8.T1).**

**Repeat grants** are exceptions issued after a denial. They appear as overturned denials and stay in the audit log.

**Latency and quotas** of the device providers can only be watched once the providers exist (B07, B08). They will be shown with the other integrations and their budget thresholds (P16.S3.T2). Answer saves and submissions never wait for a provider (`tests/test_trial_acceptance.py`, AC44).

## No hardware fingerprinting

The portal doesn't combine device characteristics into an identifier, and doesn't read hardware or advertising identifiers. A browser is never treated as a device identity. Install references don't survive a reinstall, and the portal doesn't pretend they do.
