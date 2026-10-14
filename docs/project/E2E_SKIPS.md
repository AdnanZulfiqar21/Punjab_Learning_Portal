# Skipped browser tests: what they are and why (SKIPS-01)

Written 2026-10-14 for the PR #188 review (gap 3). Source: CI run 38508838236 on PR #187's head `a357278`. In that
run the browser suite had **140 passed and 61 skipped**: 60 in the `phone` project (Pixel 7) and 1 in `iphone`.
Every skip is a `test.skip` with a stated reason. None is a failing test switched off.

| Group | Specs (skips) | Why skipped | Evidence | Action |
|---|---|---|---|---|
| Staff screens | studio (11), support (5), written-results (3), adjudication, admin-access, products, pricing, accessibility, written-reading (1 each) = **25** | Staff work at desktops; the studio, support and marking screens aren't designed or qualified for phones. Public pricing is checked at phone width in its own test, and written-reading checks reflow at 640 px. | Run on `desktop` in every CI run | None. A phone studio would be a product decision first. |
| Checks that don't depend on screen size | security-boundaries (2), payload-budget (2), visible-actions (3) = **7** | Request-level CSRF checks, payload budgets and the link crawl give the same result at any width, so they run once. | Run on `desktop` in every CI run | None |
| Keyboard journey on touch phones | browsers (2: `phone`, `iphone`) = **2** | Touch phones have no Tab key. | The same journey runs on desktop Chrome, Firefox and Safari | None |
| Learner journeys | practice (15), lessons (4), journeys (2), shared-device (2), settings (2), search (1), trial-devices (1) = **27** | Kept to `desktop` in CI to keep each run short. | **2026-10-14: run at phone width** (`E2E_FULL_MATRIX=1`, `phone` project, production build, one worker): **27 passed and 1 exceeded its 90 s budget**. That journey's phone budget is now 180 s, and it passes alone in 28 s. No phone-specific defect was found. With three workers against one local server, sign-ups timed out: that was load on the local machine (the same specs passed on `desktop` against the same server). | Run `E2E_FULL_MATRIX=1` on every release candidate (release checklist). |

Total: 25 + 7 + 2 + 27 = **61**.

## Running the full matrix

```bash
E2E_FULL_MATRIX=1 pnpm --filter web exec playwright test --project=phone --workers=1
```

Use a production build (`next build` then `next start`), as CI does. A development server compiles pages on demand
and is too slow for the longest journeys.
