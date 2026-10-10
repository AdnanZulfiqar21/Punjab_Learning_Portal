# Attack surface and ASVS applicability (P18.S1.T1)

Status: engineering record, 10 Oct 2026, written from the code at `main` after PR #93. It describes what exists, not a
deployment (none exists yet: B03). It is not an independent assessment; P18.S4.T1 (independent review) remains open.

## Trust boundaries

| # | Boundary | Who crosses it | What protects it today | Evidence |
|---|---|---|---|---|
| 1 | Browser → web app (Next.js BFF, `apps/web`) | Anyone | HTTP-only `SameSite=Lax` session cookie (`Secure` in staging/production); CSP without nonces (`script-src 'unsafe-inline'`, see gaps); security headers; `safeNext` redirect validation; server actions only | HEADERS-01, REDIRECT-01, `lib/session.ts` |
| 2 | Web BFF → API (`/v1`) | The BFF with the user's bearer token | Every non-allowlisted route needs a principal (pinned allowlist test); staff routes refuse learners with exactly 403 before lookup/validation | AUTHZ-01, OCT9-06 |
| 3 | Mobile app (Expo) → API | Learners | Same API rules; installation token for trial device decisions (no device attestation yet: B07/B08) | TRIAL-02 |
| 4 | Identity provider → API | Tokens | Production: OIDC issuer/audience with JWKS verification; the development adapter is refused at startup outside development/test | `config._validate_role` |
| 5 | Staff (studio/admin/ops) → API | Scoped staff | Role + scope checks; MFA for sensitive permissions (`MFA_REQUIRED`); two-person rules for publishing and exam profiles; audit trail (append-only trigger) | IMPL-07, AUDIT-01, EXAMPROFILE-01 |
| 6 | File intake → storage | Learners (written evidence, support screenshots), staff (imports) | Size/page/row caps; type checks with real decoders; re-encoding of images; isolated evidence worker; private storage keys never exposed | EVIDENCE-01, SUPPORT-03, IMPORT-01, CSV-01 |
| 7 | Background workers → database | Workers | Leases + `SKIP LOCKED`; one short transaction per unit; permission rechecked for exports | W06-06, EXPORTS-01 |
| 8 | API → external providers | Email/SMS/push/payments/media/assessor | None are connected (B04–B07, B10); adapters refuse development modes in deployed roles | NOTIF-01, AUTOASSESS-01 |
| 9 | Operators → database (migrations, CLIs) | Platform operators | Migrations as a separate release step with expand/contract rules; dev-only CLIs refuse non-dev roles | RELEASE-01, IMPL-01 |
| 10 | CI → repository | Contributors | Dependency audits, credential scan, contract drift, migration checks; no branch protection yet (owner setting) | SUPPLY-CHAIN-01 |

## Data classes and where they live

- **Account and session:** `app_user`, `user_session` (hashed tokens), `dev_credential` (development only).
- **Learning records:** attempts, answers, scores, notebook (with private notes), evidence, completions, analytics events
  (pseudonymous; no private words allowed in properties).
- **Written evidence:** private object keys (local directory in development; private object storage required in deployed
  roles, B03).
- **Support:** tickets, messages (internal staff notes never exported or shown to learners), screenshots.
- **Audit:** append-only; sensitive values redacted on display.
- Personal-data export covers every per-person table (inventory test); deletion requests are recorded and routed, not
  executed automatically (B15).

## ASVS 4.0.3 applicability (level 2 target)

| Chapter | Applies | Where it is met today | Gaps / owner |
|---|---|---|---|
| V1 Architecture | Yes | This map; boundaries above; release manifest | Threat model review by an independent reviewer (P18.S4.T1) |
| V2 Authentication | Partly (delegated to the IdP) | OIDC with issuer/audience/JWKS checks; MFA claim required for sensitive staff actions | Password, lockout and MFA enrolment policy belong to the chosen IdP (B03/B04 decision) |
| V3 Session | Yes | Opaque application sessions, hashed at rest, revocable, listed for the user; HTTP-only cookie | Absolute/idle timeout values to confirm at deployment |
| V4 Access control | Yes | Deny by default; scoped roles; object ownership (404 for others); exact-403 staff matrix; MFA matrix | Periodic access review process (owner) |
| V5 Validation, sanitisation | Yes | Pydantic schemas with `extra="forbid"` for content blocks; CSV formula neutralisation; redirect validation; rich text limited to registered blocks | — |
| V6 Cryptography | Partly | Argon2 for development passwords; SHA-256 for integrity; secrets via configuration with startup validation | Key management and rotation live with hosting (B03); rotation rehearsal P18.S4.T2 open |
| V7 Errors and logging | Yes | Problem-details errors without stack traces; correlation IDs; audit trail | Central log retention and access (B03) |
| V8 Data protection | Yes | `Cache-Control: private, no-store` on personal responses; result-release policy; export coverage | Retention schedule (B15) |
| V9 Communications | Deployment | HSTS/TLS are the hosting edge's job | B03 |
| V10 Malicious code | Yes | Dependency audits and credential scan in CI | SBOM and bundle/source-map checks (P18.S2.T3 remainder) |
| V11 Business logic | Yes | Idempotency keys; attempt protocol ledger; bounded exports; allowance ledger | **No application rate limiting**: anti-automation for expensive endpoints (form builds, exports, uploads) relies on caps per user today; edge rate limiting is a deployment decision (B03) |
| V12 Files and resources | Yes | Caps, decoders, re-encoding, isolated processing, private keys; ClamAV scan before storage, failing closed (UPLOAD-SCAN-01) | Running the scanner daemon (B03) |
| V13 API | Yes | Pinned public allowlist; typed contracts with drift check; no GraphQL | — |
| V14 Configuration | Yes | Startup validator refuses development settings in deployed roles; security headers; release manifest | CSP still allows inline scripts (Next.js without nonces); a nonce-based CSP needs dynamic rendering trade-offs evaluated before claiming strong script-injection protection |

## Known gaps carried forward

1. Application rate limiting (V11): decide edge vs application limits with the hosting choice (B03).
2. CSP `unsafe-inline` (V14): evaluate nonces with Cache Components before claiming strong XSS protection.
3. Running the upload scanner daemon in hosting (V12; the scan step itself exists, UPLOAD-SCAN-01).
4. SBOM and bundle/source-map checks (V10, P18.S2.T3 remainder).
5. Independent review of this map and a penetration test (P18.S4.T1): needs an external reviewer.
6. Branch protection on `main` is not enforced (owner setting); merges follow a manual green-CI rule.
