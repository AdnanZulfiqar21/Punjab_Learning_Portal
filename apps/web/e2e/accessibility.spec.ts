import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// P19 accessibility (A11Y-01): automated WCAG 2 A/AA checks with axe on the main learner pages, signed out and in.
// Serious and critical violations fail the build. Automated rules cover only part of WCAG; manual screen-reader and
// keyboard reviews are still required before release.
const AUTH = { timeout: 20_000 };

async function audit(page: Page, path: string) {
  await page.goto(path);
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
  if (!results) throw new Error(`${path}: the page kept navigating (now at ${page.url()})`);
  const blocking = results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id} (${v.impact}): ${v.help} — ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`);
  expect(blocking, `${path} (landed on ${page.url()}) accessibility violations`).toEqual([]);
}

test.describe.configure({ mode: "serial" });

for (const path of ["/", "/learn", "/search?q=cell", "/help", "/signin"]) {
  test(`signed out: ${path} has no serious accessibility violations`, async ({ page }) => {
    await audit(page, path);
  });
}

test("signed in: practice, help and account have no serious accessibility violations", async ({ page }) => {
  test.setTimeout(120_000);
  const email = `e2e-a11y-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  await page.goto("/signin?next=/account");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("a11y-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/account$/, AUTH);
  for (const path of ["/account", "/practice", "/help", "/help/new", "/notifications"]) {
    await audit(page, path);
  }
});
