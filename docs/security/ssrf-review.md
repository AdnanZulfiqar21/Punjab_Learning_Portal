# Server-side request review (SSRF)

P18.S2.T1, SECURITY-SUITE-01. Reviewed 2026-10-14 against the code on `main`. Re-review when a new outbound call,
webhook, URL import or image optimizer setting is added.

**Finding:** no server-side code fetches a URL that a learner, author or operator supplies. Every outbound request
goes to a destination fixed by deployment configuration.

## Web server (Next.js)

| Outbound call | Destination | What a user controls |
|---|---|---|
| Server components, server actions and `lib/session.ts` `api()` | `PORTAL_API_ORIGIN` (runtime configuration, validated at start) | Only the path. Identifiers are `encodeURIComponent`-escaped, and route handlers accept only UUID-shaped ids and short numeric positions |
| Same-origin upload proxies (written pages, rescans, help screenshots, studio assets, imports, lecture masters, source originals, resumable uploads) | The same API origin | The request body (streamed through) and a short query note. Each refuses a cross-site or origin-less request first (`e2e/security-boundaries.spec.ts`) |
| Sign-out | The same API origin (`DELETE /v1/me/session`) | Nothing |

There is no `next/image` use and no `images.remotePatterns`, so the image optimizer cannot be pointed at another host.
Browser-side `fetch` calls go only to this site's own route handlers.

## API (FastAPI)

| Outbound connection | Destination | What a user controls |
|---|---|---|
| Upload scanning (`system/scanning.py`) | `PORTAL_CLAMD_HOST` / `PORTAL_CLAMD_PORT` | The scanned bytes only |
| Integration status probe (`system/integrations.py`) | The same scanner address, for a 2-second ping | Nothing |
| Database | `PORTAL_DATABASE_URL` | Nothing |

Uploads (written pages, screenshots, assets, imports, lecture masters) are received as bytes and never fetched from a
URL. Email and push delivery have no provider yet (B04, B07); the automatic assessor has none either (B10). When one is
added, its endpoint must come from deployment configuration, never from a request, and this review must be updated.

## Not covered here

- HSTS and TLS at the edge (B03).
- A record of framework security advisories checked against the pinned Next.js and FastAPI versions: that needs a
  look-up against the advisory databases and is left for the dependency review (P18.S4).
