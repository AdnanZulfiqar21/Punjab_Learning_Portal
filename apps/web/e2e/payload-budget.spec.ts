import { expect, test, type Page } from "@playwright/test";

// P11.S4.T1 (PERF-01): initial client JavaScript budget per learner route, measured as transferred (compressed) bytes
// from Resource Timing on a production build. Measured 2026-10-11: 140–148 KB on every learner route (mostly the
// framework); the budget leaves ~20 % headroom so an accidental heavy import fails CI instead of reaching phones.
// Development servers ship unminified code, so this runs only against production builds (CI, or E2E_PRODUCTION=1).
const BUDGET_KB = 180;
const AUTH = { timeout: 20_000 };

test.skip(!process.env.CI && !process.env.E2E_PRODUCTION, "Budgets apply to production builds (CI runs one)");
test.skip(({ isMobile }) => isMobile, "Payload is the same for every viewport");

async function jsKB(page: Page, path: string): Promise<number> {
  await page.goto(path, { waitUntil: "networkidle" });
  return page.evaluate(() => {
    const js = performance
      .getEntriesByType("resource")
      .filter((e) => (e as PerformanceResourceTiming).initiatorType === "script" || e.name.endsWith(".js")) as PerformanceResourceTiming[];
    return Math.round(js.reduce((n, e) => n + (e.encodedBodySize || e.transferSize || 0), 0) / 1024);
  });
}

test("public routes stay within the initial JavaScript budget", async ({ page }) => {
  const over: string[] = [];
  for (const path of ["/", "/learn", "/learn/11/biology", "/learn/chapter/317f2726-31a1-55f5-bd13-a955154033e2", "/search?q=cell", "/help"]) {
    const kb = await jsKB(page, path);
    if (kb > BUDGET_KB) over.push(`${path}: ${kb} KB`);
    expect(kb, `${path} loaded no JavaScript at all`).toBeGreaterThan(0);
  }
  expect(over, `routes over ${BUDGET_KB} KB of compressed JavaScript`).toEqual([]);
});

test("learner routes, including the exam room, stay within the initial JavaScript budget", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/signin?next=/account");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(`e2e-budget-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`);
  await page.getByLabel("Password").fill("budget-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/(account|onboarding)(\?|$)/, AUTH);
  await page.goto("/practice?grade=11&subject=biology");
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByLabel("Questions", { exact: true }).fill("4");
  await page.getByRole("button", { name: "Start test" }).click();
  await expect(page).toHaveURL(/\/practice\/attempt\/[0-9a-f-]{36}$/, AUTH);
  const attempt = new URL(page.url()).pathname;
  const over: string[] = [];
  for (const path of ["/", "/practice?grade=11&subject=biology", attempt, "/practice/progress", "/study", "/account"]) {
    const kb = await jsKB(page, path);
    if (kb > BUDGET_KB) over.push(`${path}: ${kb} KB`);
  }
  expect(over, `routes over ${BUDGET_KB} KB of compressed JavaScript`).toEqual([]);
});
