# Server setup: what to do when the real server exists

The owner asked on 2026-11-12 for one place listing everything that has to be done on the server. No server exists yet (B03:
cloud account, budget and region D14). Nothing here has been done, and no item counts as evidence until it has been done
on the deployment and checked there. Add new server-only steps here as features land.

## 0. Role and core settings (SERVER-SECURITY-01, security audit 2026-11)

Set these first. The API and the web server refuse to start in a production role when one is missing or still a
development value (`apps/api/src/portal_api/config.py`, `apps/web/src/lib/runtime-config.ts`).

| Setting | Where | Value | Notes |
|---|---|---|---|
| `PORTAL_ROLE` | API and web | `production` (or `staging`) | The images set `production` already (ROLE-EXPLICIT-01). Outside the images it must be set by hand: without it both start with development defaults |
| `PORTAL_BUILD_ID` | API | the release commit or image digest | `local` is refused |
| `PORTAL_DATABASE_URL` | API | the server's database | Development hosts and credentials are refused |
| `PORTAL_PUBLIC_API_ORIGIN` | API | the API's public `https://` address | |
| `PORTAL_EVIDENCE_STORE` | API | `s3`, with `PORTAL_EVIDENCE_S3_ENDPOINT`, `_BUCKET`, `_ACCESS_KEY`, `_SECRET_KEY` | The local directory is refused. Use an `https://` endpoint. Create the bucket by hand with public access blocked |
| `PORTAL_UPLOAD_SCANNER` | API | `clamd`, with `PORTAL_CLAMD_HOST` and `PORTAL_CLAMD_PORT` | Needs a running ClamAV. Set `StreamMaxLength 45M` in `clamd.conf`: the default 25M is below the 40 MB upload limit |
| `PORTAL_TRIAL_DEVICE_EVIDENCE` | API | `required` or `fallback` | Must be chosen explicitly |
| `PORTAL_TRIAL_REF_PEPPER` | API | a new random secret | The development value is refused |
| `PORTAL_MFA_SECRET_KEY` | API | a new random secret, 32 characters or more | Encrypts staff authenticator secrets (STAFF-MFA-01). Keep it for the life of the deployment: if it changes, everyone sets two-step sign-in up again |

The web server's production check refuses an API address on `localhost` or `127.0.0.1`. On a single machine, give the
API an internal host name (a compose service name or a hosts-file entry) and use that in `PORTAL_API_INTERNAL_ORIGIN`.
Do not leave the role unset to get round the check.

## 1. Sign-up, sign-in and email (AUTH-PASSWORD-01, #560)

The portal's own email and password sign-up sends a 6-digit code through Resend. The same email route sends the
forgotten-password code.

| Setting (API environment) | Value | Notes |
|---|---|---|
| `PORTAL_NOTIFICATION_EMAIL_ADAPTER` | `resend` | `dev_outbox` is refused outside development and test |
| `PORTAL_RESEND_API_KEY` | the Resend key | Owner's existing key works (checked 2026-11-12, no rotation needed). Copy it from the owner's secrets file into the server's secret store; never into the repo, an image or a log |
| `PORTAL_EMAIL_FROM` | `Sirf Concepts <no-reply@sirfconcepts.com>` | The domain `sirfconcepts.com` is already verified in Resend (region eu-west-1). Production refuses a `resend.dev` sender |
| `PORTAL_PASSWORD_AUTH_SIGNING_KEY` | a **new** RSA private key, 2048 bits or more, PEM | Generate it on the server or in its secret store, one per environment (staging and production differ). Without it the startup validator refuses to start |
| `PORTAL_PASSWORD_AUTH_ISSUER` | the API's public `https://` address | Must not be a development issuer |
| `PORTAL_DEV_AUTH_ENABLED` | `false` | Turns off the code-free development registration and simulated MFA |

The API refuses to start in a staging or production role when any of these is missing or wrong (`config.py`, the
deployed-role validator). Check that by starting it once with one setting removed.

After the first deploy:
- Sign up with a real address the owner controls, receive the code, confirm it, sign out and back in.
- Use "Forgot password?" on that account and check the code arrives and the new password works.
- In the Resend dashboard, check both emails show as delivered.

## 2. Database

- Run `alembic upgrade head` as its own release step before the new API starts. It is never run on startup.
  The sign-up work adds `7e3a9c1d5b20` (email codes), `9b4d2e6f8a10` (first name and surname) and `c3f1a7e9d520`
  (password-reset codes).
- Take a backup before the first migration on a database that holds real users.

## 3. Web and app addresses

- Web: `PORTAL_API_INTERNAL_ORIGIN` (the API address the web server calls; required in deployed roles, and production
  refuses a development host) and `PORTAL_PUBLIC_ORIGIN` (`https://sirfconcepts.com`; PUBLIC-SITE-01, then check `robots.txt` and `sitemap.xml` live).
- API: `PORTAL_CORS_ORIGINS` lists only the live web address; production refuses development or staging origins.
- Mobile: preview and production builds need `PORTAL_API_ORIGIN` set at build time (`apps/mobile/app.config.ts`
  throws without it). Build a new app version once the API address is final.

## 4. Other deployment items already recorded

- Import workers per `docs/production/import-worker.md` (IMPORT-DEPLOY-01).
- `PORTAL_ASSET_DIR` on private durable storage and the scheduled jobs in `docs/project/RESUME_STATE.md`
  ("Deployment prerequisites").
- The release manifest, requalification check and advisory review in `docs/project/RELEASE_CHECKLIST.md`.

## 5. Security steps (SERVER-SECURITY-01, security audit 2026-11)

None of these is done by the application itself. Each one must be set up on the server and checked there.

**In front of the API and the web server (reverse proxy)**
- TLS on both public addresses, a redirect from http to https, and `Strict-Transport-Security: max-age=31536000;
  includeSubDomains`.
- A per-address rate limit on `/v1/auth/*` (start with 10 requests a minute) and a general limit on the rest.
- Request-body limits: 41 MB on `/v1/written-attempts/*/pages` and the rescan route, a few hundred MB only on the
  staff upload routes, 1 MB everywhere else. A body timeout and a limit on connections per address.
- Pass the real client address on to the API (`X-Forwarded-For`), and pass `Host` through unchanged: the web upload
  and sign-out routes compare `Origin` with `Host` and refuse a mismatch.
- `/readyz` and `/openapi.json` reachable from the load balancer or the private network only.

**Database**
- Two database roles: an owner that runs migrations, and a runtime role for the API and workers with data changes
  only (no table changes, no `TRUNCATE`; on `audit_event` insert and read only).
- Backups from the first day, and one tested restore before real users sign up.
- Postgres, the cache and the object store are never reachable from the internet. `infra/docker-compose.yml` is for
  a laptop only.

**Moving content to the server**
- Move content and catalogue tables only. Never copy `app_user`, `dev_credential`, `staff_role_grant`,
  `user_session` or any other per-person table from a development database: it holds fixture staff accounts whose
  password is in this public repository.
- After loading, check that no active staff role belongs to a development-issuer account.

**Processes and storage**
- Run both containers as a non-root user.
- A persistent volume shared by the API and its workers for master uploads, source originals, bulk-import files and
  export files (these are written to local disk even with `PORTAL_EVIDENCE_STORE=s3`).
- Schedule the orphan sweep, export expiry and upload reconcile commands.

**Staff two-step sign-in (STAFF-MFA-01)**
- The first owner: sign up, then `portal-grant-role --email … --role owner_admin --reason …` on the server.
- Every staff member turns on two-step sign-in under Account, with an authenticator app, and keeps the recovery codes.
  Publishing, roles, finance, audit and operations answer 403 until the code has been entered on that device (it
  lasts twelve hours).
- A lost phone with no recovery codes: `portal-mfa-reset --email … --reason …` on the server, after checking who is
  asking. Never loosen the MFA list or enable the development sign-in instead.

**After every deploy (smoke checks)**
- `POST /v1/dev-auth/token` answers 404 and `/docs` answers 404.
- `GET /v1/runtime-config` says `production` and lists only `password` under `sign_in_methods`.
- Signing in on the website sets a cookie marked `Secure` and `HttpOnly`.
- The http address redirects to https, and the https answer carries the `Strict-Transport-Security` header.

## Not built yet (needed before using these features live)

- Promotional emails: sign-up stores an opt-in only. A campaign sender still has to check consent and the suppression
  list and add an unsubscribe link before any promotion is sent.
