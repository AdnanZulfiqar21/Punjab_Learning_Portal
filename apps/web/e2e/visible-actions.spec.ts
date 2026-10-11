import { expect, test, type Page } from "@playwright/test";

// P11.S4.T3 (ACTIONS-01): every link a learner can see leads somewhere real, and no page shows placeholder text.
// Crawls internal links breadth-first from the main entry points (signed out, then as a new learner), two levels deep,
// and checks each response. Lessons, chapters and attempts are sampled, not exhaustively visited.
const AUTH = { timeout: 20_000 };
const PLACEHOLDER = /lorem ipsum|\bTODO\b|coming soon|placeholder|under construction/i;
const SKIP = [/\/signout/, /\/assets\//, /\.(pdf|png|jpe?g|svg)$/i, /^\/_next\//];

async function crawl(page: Page, starts: string[], maxPages: number) {
  const seen = new Set<string>();
  const queue = starts.map((p) => ({ path: p, depth: 0 }));
  const problems: string[] = [];
  const perPrefix = new Map<string, number>();
  while (queue.length && seen.size < maxPages) {
    const { path, depth } = queue.shift()!;
    if (seen.has(path)) continue;
    // Sample families of similar pages (each chapter, each attempt) instead of visiting all of them.
    const family = path.replace(/[0-9a-f]{8}-[0-9a-f-]{27}/gi, ":id").replace(/\/\d+(\/|$)/g, "/:n$1");
    const count = perPrefix.get(family) ?? 0;
    if (count >= 2) continue;
    perPrefix.set(family, count + 1);
    seen.add(path);
    // Probe with the page's session first: a link that serves a file (an export, a report, a handout) is checked as a
    // download instead of being navigated to.
    const probe = await page.request.get(path, { maxRedirects: 0 }).catch(() => null);
    if (probe && (probe.headers()["content-disposition"] ?? "").startsWith("attachment")) {
      if (probe.status() >= 400) problems.push(`${path}: download HTTP ${probe.status()}`);
      continue;
    }
    const res = await page.goto(path);
    const status = res?.status() ?? 0;
    if (status >= 400) problems.push(`${path}: HTTP ${status}`);
    await expect(page.locator("main")).toBeVisible(AUTH);
    await page.waitForLoadState("networkidle", { timeout: 5_000 }).catch(() => undefined);
    const text = await page.locator("main").innerText();
    if (PLACEHOLDER.test(text)) problems.push(`${path}: placeholder text "${PLACEHOLDER.exec(text)![0]}"`);
    if (/We couldn.t load this page|Something went wrong/.test(text)) problems.push(`${path}: error page shown`);
    if (depth >= 2) continue;
    const hrefs = await page.locator("a[href^='/']").evaluateAll((as) => as.map((a) => a.getAttribute("href")!.split("#")[0]));
    for (const h of new Set(hrefs)) {
      if (h && !seen.has(h) && !SKIP.some((r) => r.test(h))) queue.push({ path: h, depth: depth + 1 });
    }
  }
  return { problems, visited: seen.size };
}

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile, "The link crawl runs on desktop");

test("signed out: every visible link resolves and no page shows placeholder text", async ({ page }) => {
  test.setTimeout(240_000);
  const { problems, visited } = await crawl(page, ["/", "/learn", "/search?q=cell", "/help", "/signin"], 60);
  expect(visited).toBeGreaterThan(10);
  expect(problems).toEqual([]);
});

test("signed in: every visible link resolves and no page shows placeholder text", async ({ page }) => {
  test.setTimeout(300_000);
  const email = `e2e-actions-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  await page.goto("/signin?next=/account");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("actions-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/(account|onboarding)(\?|$)/, AUTH);
  const { problems, visited } = await crawl(
    page,
    ["/", "/account", "/practice", "/practice/progress", "/practice/notebook", "/practice/mocks", "/study", "/notifications", "/help"],
    70,
  );
  expect(visited).toBeGreaterThan(12);
  expect(problems).toEqual([]);
});

test("staff: every visible studio and admin link resolves and no page shows placeholder text", async ({ page }) => {
  test.setTimeout(420_000);
  for (const [email, starts] of [
    ["studio-author@example.com", ["/studio", "/studio/overview", "/studio/assets", "/studio/lectures", "/studio/imports"]],
    ["studio-support@example.com", ["/studio/support", "/studio/support/learners"]],
    ["studio-owner@example.com", ["/account", "/studio/lectures"]],
  ] as const) {
    await page.context().clearCookies();
    await page.goto("/signin?next=/account");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("studio-fixture-pass-1");
    await page.getByLabel(/Simulate a multi-factor sign-in/).check();
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page).toHaveURL(/:\d+\/account$/, AUTH);
    const { problems, visited } = await crawl(page, [...starts], 45);
    expect(visited, email).toBeGreaterThan(3);
    expect(problems, email).toEqual([]);
  }
});
