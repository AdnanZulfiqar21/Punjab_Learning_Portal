# Server setup: what to do when the real server exists

The owner asked on 2026-11-12 for one place listing everything that has to be done on the server. No server exists yet (B03:
cloud account, budget and region D14). Nothing here has been done, and no item counts as evidence until it has been done
on the deployment and checked there. Add new server-only steps here as features land.

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

## Not built yet (needed before using these features live)

- Promotional emails: sign-up stores an opt-in only. A campaign sender still has to check consent and the suppression
  list and add an unsubscribe link before any promotion is sent.
- Real staff MFA (the development simulation is off in deployed roles).
