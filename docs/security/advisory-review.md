# Dependency and framework advisory review

P18.S2.T3 and P18.S4.T3, ADVISORY-REVIEW-01. Checked 2026-10-14 against the lockfiles on `feat/mobile-transforms`
(the same dependency versions as `main` at `b6996e7`). This is an engineering check, not the independent security
review that P18.S4.T1 requires. Re-run it on the release candidate's lockfiles within 7 days of a release, and after
any framework upgrade.

CI already fails a change on any Python advisory and on JavaScript advisories rated high or above (SUPPLY-CHAIN-01).
This review adds what CI does not check: moderate JavaScript findings, and a direct look-up of each main framework
version in the GitHub advisory database.

## Method

| Check | Command | Result |
|---|---|---|
| Python runtime dependencies (38 pinned packages) | `uv export --frozen --no-dev --no-hashes --no-emit-project`, then `uvx pip-audit==2.9.0 -r …` | No known vulnerabilities |
| JavaScript production dependencies, every severity | `pnpm audit --prod` | 2 high (both reviewed exceptions, below), 2 moderate (new, below) |
| Framework versions in the GitHub advisory database | `gh api -X GET advisories -f ecosystem=… -f affects=<package>@<version>` | No advisory affects any version listed below |

The advisory query was checked against known-affected versions first: `next@14.0.0` and `starlette@0.27.0` both
return their published advisories, so an empty answer means none is recorded, not that the query failed.

Versions looked up:

- **Web:** next 16.4.0, react and react-dom 19.3.0, react-server-dom-turbopack 19.3.0.
- **Mobile:** expo 57.0.27, react-native 0.86.3, expo-router 57.0.25, expo-image 57.0.5, expo-secure-store 57.0.4.
- **API:** fastapi 0.142.2, starlette 1.7.0, sqlalchemy 2.1.3, pydantic 2.13.5, uvicorn 0.54.0, h11 0.16.0,
  pillow 12.3.0, psycopg 3.3.6, alembic 1.20.0, pyjwt 2.15.1, argon2-cffi 25.1.0, cryptography 50.0.2.
  python-multipart is not a dependency: uploads are read as raw request bodies.

## Findings

| Advisory | Package and path | Severity | Ships to users? | Decision |
|---|---|---|---|---|
| GHSA-7wch-p9px-956x, GHSA-jc66-7q78-782g, GHSA-8hrf-8g6f-7xwp, GHSA-hqq3-7jhf-c5jx, GHSA-5x38-2vff-x55p | node-forge ≤1.4.0 via `@expo/cli` (published 2026-10-31) | High | No: mobile build tooling | Fixed (#456): override `@expo/cli>node-forge` ^1.4.1, resolves to 1.4.2. With it, GHSA-86w9-cpqp-85rv and GHSA-vfj7-8cjw-p6xm no longer match any installed package; their ignores can be dropped |
| GHSA-86w9-cpqp-85rv | node-forge via `@expo/cli` | High | No: mobile build tooling | Reviewed exception (SUPPLY-CHAIN-01); no patched version listed |
| GHSA-vfj7-8cjw-p6xm | braces via Metro | High | No: mobile bundler | Reviewed exception (SUPPLY-CHAIN-01); no patched version listed |
| GHSA-qr28-fpjm-wq7f | decode-uri-component ≤0.5.0 via `expo-router` → `query-string` 7.1.3 (published 2026-10-29) | High | Yes: the mobile app parses links with it | Reviewed exception (SUPPLY-CHAIN-01, 2026-10-29), below |
| GHSA-vcc3-ghjq-m6fr | decode-uri-component ≤0.4.2 via `expo-router` → `query-string` 7.1.3 | Moderate | Yes: the mobile app parses links with it | Residual risk, below |
| GHSA-w5hq-g745-h8pq | uuid <11.1.1 via `expo` → `@expo/config-plugins` → `xcode` | Moderate | No: runs only while generating native projects | Residual risk, below |

### Residual risks

**decode-uri-component (GHSA-vcc3-ghjq-m6fr).**
- *Exposure:* a malformed, heavily percent-encoded link opened in the mobile app could make the app slow or hang on that one device. The server, other learners and stored data are not affected. The web app does not use this package.
- *Why not patched now:* the fixed release (0.5.0) is an ES module only, while `query-string` 7.1.3 loads it with `require()`. Forcing it through an override would probably break link parsing in the app, and that cannot be verified without a device (B09, B14).
- *Owner:* engineering (mobile).
- *Target:* the first Expo SDK update that ships a fixed `query-string`, and in any case before the mobile release candidate (P19). Proposed date 2026-12-31.

**decode-uri-component (GHSA-qr28-fpjm-wq7f, high; reviewed exception added 2026-10-29).**
- *What:* quadratic time in the fallback decoder on malformed input with many distinct percent-encoded runs (about 224 KB to block for ~20 s). Availability only. Same package, path and exposure as GHSA-vcc3-ghjq-m6fr above.
- *Exposure:* only a malformed link of that size opened in the mobile app, which could freeze the app on that one device. The server, other learners and stored data are not affected; the API does not use this package and the web app does not either (`pnpm audit` lists only `apps__mobile>expo-router>query-string`).
- *Why an exception and not an override:* the only fixed release, 0.5.1 (published 2026-10-23), is an ES module only, while `query-string` 7.1.3 loads it with `require()` and asks for `^0.2.2`, so forcing it would probably break link parsing in the app, which cannot be verified without a device (B09, B14).
- *Re-check:* remove the ignore as soon as `expo-router` ships a `query-string` that works with a fixed release, at every Expo SDK update, and in any case before the mobile release candidate (P19). Proposed date 2026-12-31.

**uuid (GHSA-w5hq-g745-h8pq).**
- *Exposure:* none for users. The `xcode` package uses uuid while `expo prebuild` writes the iOS project. The flaw is in v3/v5/v6 called with an output buffer; `xcode` 3.0.1 only calls `uuid.v4()` with no arguments.
- *Owner:* engineering (mobile).
- *Target:* the next Expo SDK update. Proposed date 2026-12-31.

Neither moderate finding is release-blocking under P18.S4.T3, which covers P0/P1 findings and confirmed
critical/high exploitable issues. Both stay open here until fixed.
