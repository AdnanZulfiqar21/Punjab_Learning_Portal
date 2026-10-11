# Supported browsers (P19.S2.T1, BROWSERS-01)

What we test, and what we don't claim. Each row is backed by the CI journeys in `apps/web/e2e/browsers.spec.ts` (core
journeys: browse to a chapter and read a preview lesson with images, keyboard-only sign-up, start/answer/submit a
practice test) plus, for Chromium, the full suite including axe accessibility scans.

| Engine | Browsers it covers | Tested in CI | Supported range (initial policy) |
|---|---|---|---|
| Chromium | Chrome, Edge, Samsung Internet, Opera, Android WebView | Full suite: desktop (Desktop Chrome) and phone (Pixel 7) | Current and the previous two major versions |
| Gecko | Firefox | Cross-browser journeys (Desktop Firefox) | Current release and current ESR |
| WebKit | Safari on macOS; every browser on iPhone/iPad | Cross-browser journeys (Desktop Safari, iPhone 13) | Safari 17+ / iOS 17+ |

## Known limitations

- **Safari keyboard focus:** Safari only moves focus to links with Tab when *Press Tab to highlight each item* is on (it is
  off by default). Every control remains reachable; the skip link is checked in Chromium and Firefox.
- **Emulation, not devices:** WebKit and phone runs are Playwright engines and device profiles, not physical devices.
  Physical-device checks need named reference devices (B09).
- **Not tested:** Internet Explorer (unsupported), pre-Chromium Edge (unsupported), UC Browser and KaiOS (no plan to
  support until owner research says otherwise).
- **Local note:** on the development laptop (2026-10-11) Playwright's Firefox build fails to start (Windows side-by-side
  configuration error), so Firefox evidence comes from CI (Ubuntu) only.
- Old browsers that can't run the app still receive server-rendered pages, but interactive features (the exam room, study
  tools) need JavaScript and are not promised there.
