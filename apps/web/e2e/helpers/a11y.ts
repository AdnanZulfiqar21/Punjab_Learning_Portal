import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

// P19 accessibility (A11Y-01): automated WCAG 2 A/AA checks with axe. Serious and critical violations fail the build.
// Automated rules cover only part of WCAG; manual screen-reader and keyboard reviews are still required before release.

/** Open `path` (unless it is null: scan the current page) and fail on serious or critical axe violations. */
export async function audit(page: Page, path: string | null) {
  if (path !== null) await page.goto(path);
  await expect(page.locator("main")).toBeVisible();
  // Let streamed sections settle, without depending on the network ever going fully idle.
  await page.waitForLoadState("networkidle", { timeout: 5_000 }).catch(() => undefined);
  let results: Awaited<ReturnType<AxeBuilder["analyze"]>> | null = null;
  for (let tries = 0; tries < 3 && !results; tries++) {
    try {
      results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    } catch (e) {
      if (!String(e).includes("Execution context was destroyed")) throw e;
      await page.waitForLoadState("load"); // the page navigated on its own (e.g. a client redirect): scan where it landed
    }
  }
  const where = path ?? page.url();
  if (!results) throw new Error(`${where}: the page kept navigating (now at ${page.url()})`);
  const blocking = results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id} (${v.impact}): ${v.help} — ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`);
  expect(blocking, `${where} (landed on ${page.url()}) accessibility violations`).toEqual([]);
}

/** 200 % zoom on a 1280 px window is a 640 px layout: nothing may need sideways scrolling (WCAG 1.4.10 reflow). */
export async function reflows(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, `${page.url()} scrolls sideways at this width`).toBeLessThanOrEqual(1);
}
