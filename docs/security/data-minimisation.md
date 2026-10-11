# Data minimisation review (P18.S3.T1, MINIMISATION-01)

Reviewed 2026-10-11 against the code on `main`. This covers what the portal collects about a person and why. It is a
code-level review. It does not replace the approved privacy notice and retention schedule (BLOCKERS B15) or the review
of the real deployment's processors (B03-B06), which can only happen once those exist.

## What is collected, and why

| Where | Personal data | Why it is needed | Notes |
|---|---|---|---|
| `app_user` | email, display name, issuer subject, last seen | Sign-in, contact, account recovery | No phone, address, date of birth, school or identity document (CNIC) is collected anywhere. |
| `student_profile` | class, stream, subjects, target exams and year, explanation language, daily minutes | Choosing content, patterns and the study plan | Explicit fields only. The unused free-form `preferences` column was retired here (see below). The field set is pinned by `tests/test_data_minimisation.py`. |
| `user_session` | session token **hash**, device label, user agent (cut to 400 characters), MFA flag, times | Lets a person see and revoke their sessions | No IP address is stored. On mobile the device label is the manufacturer and model name only (`expo-device`); no device identifier is read. |
| `consent_record` | which document version was accepted or withdrawn, and when | Proof of consent | |
| Trial tables | surface, installation **reference** (peppered SHA-256 of a random per-install token), adapter verdict and detail | One free trial per person and device | No hardware identifier, advertising ID, phone number or attestation token is stored. Only the verdict is kept. |
| Attempts, answers, scores, notebook, plan | the learner's own answers and results | The learning product itself | Analytics events never record the option chosen. |
| Written answers | page images, re-encoded as fresh PNGs | Marking | Camera and location metadata are removed by re-encoding. |
| Help requests | subject, messages, screenshots (re-encoded PNGs) | Support | Screenshot metadata is removed. JPEG EXIF, including GPS, is checked in `tests/test_data_minimisation.py`; PNG text chunks in `test_support_attachments.py`. |
| `notification` | title, body, link | In-app notices | |
| `analytics_event` | user ID plus dictionary-validated properties | Product funnels and learning reports | Free text is impossible: every property is declared and type-checked (ANALYTICS-EVENTS-01). Checkpoint answers are never recorded. |
| `audit_event` | actor ID, action, target, details | Accountability for staff and security actions | |
| Server logs | method, path (no query string), status, timing, correlation ID | Operations | No body, header, token or password is logged (`tests/test_exposure.py`). |

## Removed in this review

* `student_profile.preferences`: a free-form JSON column created in the first identity migration. It was never written
  or read: the profile API forbids unknown fields and has no such field. The model no longer maps it. Migration
  `b5d2e8a4c719` gives it a default so the column can be dropped safely. A later release drops it (expand/contract, see
  `RETIRING_COLUMNS` in `src/portal_api/release.py`).

## Third-party code in the clients

* **No session replay, heatmap, crash-reporting or analytics SDK** is installed in web or mobile (checked in
  `apps/web/package.json` and `apps/mobile/package.json`). Lessons and exams are therefore not recorded by any
  third party. Adding such an SDK needs a new review, and replay must stay off for lessons and exams.
* **Device attestation:** no platform attestation SDK (Play Integrity, App Attest) is integrated yet. The trial uses an
  opaque random per-installation token, stored only as a peppered hash. When an attestation adapter arrives, only its
  verdict may be stored, not the raw token.
* The browser bundle is checked in CI for source maps and credentials (EXPOSURE-01).

## Not yet reviewable (external)

* Real processors (hosting, email, storage, payment): B03-B06. Each needs its own data-processing review before launch.
* Retention periods and automatic deletion: B15. Today nothing is erased automatically (PRIVACY-01).
* Support exports and help-desk tooling: no third-party help desk is used; support works inside the portal.
