// §6.2b journey timings in a LAB EMULATION (P11.S4.T1, PERF-01). Not device evidence: §6.2b budgets are measured on
// named devices (B09). Runs Chromium against a production web build with network emulation (healthy 4/1 Mbps 150 ms;
// degraded 1/0.5 Mbps 300 ms) and 4x CPU throttling, using a new fixture learner and technical fixture questions.
// Measures start -> first usable question, reopen interrupted attempt -> usable with answers, tap -> visible selection
// (Event Timing: input to next paint) and tap -> "saved" (includes the 400 ms save debounce).
// Run on a quiet machine: on a shared laptop the same run varied up to 5x (2026-10-11).
//   BASE=http://localhost:3102 node scripts/measure-journeys.mjs [samples]
import { chromium } from "@playwright/test";
const BASE = process.env.BASE || "http://localhost:3100";
const N = Number(process.argv[2] || 8);
const PROFILES = {
  healthy: { offline: false, latency: 150, downloadThroughput: (4 * 1024 * 1024) / 8, uploadThroughput: (1 * 1024 * 1024) / 8 },
  degraded: { offline: false, latency: 300, downloadThroughput: (1 * 1024 * 1024) / 8, uploadThroughput: (0.5 * 1024 * 1024) / 8 },
};
const p95 = (xs) => { const s = [...xs].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.ceil(0.95 * s.length) - 1)]; };
const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 412, height: 915 } });
  const page = await ctx.newPage();
  page.setDefaultTimeout(60000);
  await page.goto(`${BASE}/signin?next=/account`);
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(`journey-check-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("practice-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(/:\d+\/(account|onboarding)(\?|$)/);
  await page.goto(`${BASE}/practice?grade=11&subject=biology`);
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await page.getByText(/Free trial until/).waitFor();

  const cdp = await ctx.newCDPSession(page);
  for (const [name, net] of Object.entries(PROFILES)) {
    await cdp.send("Network.enable");
    await cdp.send("Network.emulateNetworkConditions", net);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    const start = [], reopen = [], select = [], save = [];
    for (let i = 0; i < N; i++) {
      await page.goto(`${BASE}/practice?grade=11&subject=biology`);
      await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
      await page.getByLabel("Questions", { exact: true }).fill("5");
      const t0 = Date.now();
      await page.getByRole("button", { name: "Start test" }).click();
      const firstOption = page.getByRole("group", { name: /Options for question 1/ }).getByRole("radio").first();
      await firstOption.waitFor({ state: "visible" });
      await expectEnabled(firstOption);
      start.push(Date.now() - t0);

      // In-page timing: Event Timing duration of the tap (input to next paint) and tap -> "all saved" text.
      await page.evaluate(() => {
        window.__lat = { tap: 0, savedAt: 0, eventDur: 0 };
        new PerformanceObserver((list) => {
          for (const e of list.getEntries()) if (["pointerdown", "pointerup", "click"].includes(e.name)) window.__lat.eventDur = Math.max(window.__lat.eventDur, e.duration);
        }).observe({ type: "event", durationThreshold: 16, buffered: false });
        document.addEventListener("pointerdown", () => { window.__lat.tap = performance.now(); }, { capture: true, once: true });
        new MutationObserver(() => {
          if (!window.__lat.savedAt && document.body.innerText.includes("1 answered · all saved")) window.__lat.savedAt = performance.now();
        }).observe(document.body, { subtree: true, childList: true, characterData: true });
      });
      await firstOption.click();
      await page.getByText("1 answered · all saved").waitFor();
      await page.waitForTimeout(300); // let the event-timing entry arrive
      const lat = await page.evaluate(() => window.__lat);
      select.push(Math.round(lat.eventDur || 16)); // durationThreshold 16: below that, the tap painted within a frame
      save.push(Math.round(lat.savedAt - lat.tap));

      const url = page.url();
      await page.goto(`${BASE}/learn`); // leave mid-attempt
      const r0 = Date.now();
      await page.goto(url);
      await page.getByText("1 answered · all saved").waitFor();
      reopen.push(Date.now() - r0);
    }
    console.log(`${name} (n=${N}, CPU 4x): start->first usable question p50 ${median(start)} ms p95 ${p95(start)} ms | reopen->usable with answers p50 ${median(reopen)} p95 ${p95(reopen)} | tap->selected (event timing) p95 ${p95(select)} | tap->saved p50 ${median(save)} p95 ${p95(save)}`);
  }
  await browser.close();
})().catch((e) => { console.error("FAILED:", e.message.split(String.fromCharCode(10))[0]); process.exit(1); });

async function expectEnabled(locator) {
  for (let i = 0; i < 200; i++) { if (await locator.isEnabled()) return; await new Promise((r) => setTimeout(r, 25)); }
  throw new Error("option never became enabled");
}
