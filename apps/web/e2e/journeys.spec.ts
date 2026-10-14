import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Browser, type Page } from "@playwright/test";

// P19.S1.T1 (JOURNEYS-01): new-to-returning learner journeys across two devices, on the free trial and on staff-granted
// access. Uses the technical fixture questions and lessons from `portal-dev-seed-practice` (Class XI Biology, chapter
// 1, whose stems say which option is the key) and synthetic accounts. Not academic content.
const API = process.env.PORTAL_API_INTERNAL_ORIGIN ?? "http://127.0.0.1:8100";
const AUTH = { timeout: 20_000 };
const newEmail = (tag: string) => `e2e-${tag}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile && !process.env.E2E_FULL_MATRIX, "Two-device journeys run on desktop");

async function register(browser: Browser, email: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto("/signin?next=/account");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("journey-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/(account|onboarding)/, AUTH);
  return page;
}

/** The same account on another device: a separate browser context with its own session. */
async function signInElsewhere(browser: Browser, email: string, next = "/"): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`/signin?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("journey-fixture-pass-1");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`:\\d+${next === "/" ? "/$" : next.replace(/[?]/g, "\\?")}`), AUTH);
  return page;
}

async function onboardBiologyXI(page: Page) {
  await page.goto("/onboarding");
  await page.getByLabel("Class XI", { exact: true }).check();
  await page.getByLabel("Biology", { exact: true }).check();
  await page.getByLabel("Minutes per day").fill("30");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page).toHaveURL(/\/learn$/, AUTH);
}

async function openFirstBiologyChapter(page: Page) {
  await page.goto("/learn");
  await page.getByRole("region", { name: "Class XI", exact: true }).getByRole("link", { name: /Biology/ }).click();
  await page.getByRole("link", { name: /Chapter 1(?!\d)/ }).first().click();
  await expect(page.getByRole("region", { name: "Lessons" })).toBeVisible(AUTH);
}

async function startTest(page: Page, count: number) {
  await page.goto("/practice?grade=11&subject=biology");
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByLabel("Questions", { exact: true }).fill(String(count));
  await page.getByRole("button", { name: "Start test" }).click();
  await expect(page).toHaveURL(/\/practice\/attempt\/[0-9a-f-]{36}$/, AUTH);
}

/** The fixture stem names its key ("Which option is o3?"); pick that option, or a deliberately wrong one. */
async function answer(page: Page, correct: boolean) {
  const stem = await page.getByRole("region", { name: /Question \d+/ }).innerText();
  const key = /Which option is (o\d)\?/.exec(stem)![1];
  const choice = correct ? key : ["o1", "o2", "o3", "o4"].find((o) => o !== key)!;
  await page.getByRole("group", { name: /Options for question/ }).getByLabel(new RegExp(`Fixture option ${choice}$`)).check();
}

test("a new learner starts on one device and carries on as a returning learner on another", async ({ browser }) => {
  test.slow(); // two devices, onboarding, a test and a result: over 30 s on a development server
  const email = newEmail("journey");
  // New: register, choose a class and subject, start the free trial.
  const first = await register(browser, email);
  await onboardBiologyXI(first);
  await first.goto("/account");
  await first.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(first.getByText(/Free trial until/)).toBeVisible(AUTH);
  // Learn, then start a test and leave it half done.
  await openFirstBiologyChapter(first);
  await expect(first.getByText("Technical fixture premium lesson text.")).toBeVisible();
  await startTest(first, 4);
  await answer(first, true);
  await expect(first.getByRole("status").first()).toHaveText(/1 answered · all saved/, AUTH);
  await first.getByRole("button", { name: "Next →" }).click();
  await answer(first, false);
  await expect(first.getByRole("status").first()).toHaveText(/2 answered · all saved/, AUTH);
  const attemptUrl = first.url();

  // Returning, on another device: the dashboard shows the unfinished test and where learning stopped.
  const second = await signInElsewhere(browser, email);
  const unfinished = second.getByRole("region", { name: "Unfinished tests" });
  await expect(unfinished).toContainText("2 of 4 answered", AUTH);
  await expect(second.getByRole("region", { name: "Continue learning" })).not.toContainText("Nothing in progress");
  const axe = await new AxeBuilder({ page: second }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);

  // The test moves here explicitly, keeps both saved answers, and is finished on this device.
  await unfinished.getByRole("link", { name: /Continue practice test/ }).click();
  await expect(second).toHaveURL(attemptUrl, AUTH);
  await expect(second.getByText("This test is open on another device.")).toBeVisible(AUTH);
  await second.getByRole("button", { name: "Continue here" }).click();
  await expect(second.getByRole("button", { name: /Question 1: saved/ })).toBeVisible(AUTH);
  await expect(second.getByRole("button", { name: /Question 2: saved/ })).toBeVisible();
  await second.getByRole("button", { name: /Question 3:/ }).click();
  await answer(second, true);
  await second.getByRole("button", { name: /Question 4:/ }).click();
  await answer(second, false);
  await expect(second.getByRole("status").first()).toHaveText(/4 answered · all saved/, AUTH);
  await second.getByRole("button", { name: "Finish test" }).click();
  await second.getByRole("dialog", { name: "Submit your test?" }).getByRole("button", { name: "Submit" }).click();
  await expect(second).toHaveURL(/\/result$/, AUTH);
  await expect(second.getByText("4 of 4 answered · submitted by you")).toBeVisible(AUTH);

  // Back on the first device: submitted there too, nothing unfinished, the same result, two mistakes to revise.
  await first.goto(attemptUrl);
  await expect(first.getByRole("heading", { name: "Test submitted" })).toBeVisible(AUTH);
  await first.goto("/");
  await expect(first.getByRole("region", { name: "Recent results" })).toContainText("2 / 4", AUTH);
  await expect(first.getByRole("region", { name: "Unfinished tests" })).toHaveCount(0);
  await expect(first.getByRole("region", { name: "Today's revision" })).toContainText("2 open in your notebook");
  await first.goto("/practice/notebook");
  await expect(first.getByRole("list", { name: "Notebook entries" }).getByRole("listitem")).toHaveCount(2, AUTH);
});

test("a learner with staff-granted access practises without using the free trial", async ({ browser, request }) => {
  const email = newEmail("journey-pilot");
  const learner = await register(browser, email);
  // Finance grants labelled pilot access through the API (no payments exist yet, B06).
  const staff = await (await browser.newContext()).newPage();
  await staff.goto("/signin?next=/account");
  await staff.getByLabel("Email").fill("studio-finance@example.com");
  await staff.getByLabel("Password").fill("studio-fixture-pass-1");
  await staff.getByLabel(/multi-factor/i).check();
  await staff.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(staff).toHaveURL(/:\d+\/account/, AUTH);
  const token = (await staff.context().cookies()).find((c) => c.name === "portal_session")!.value;
  const grant = await request.post(`${API}/v1/admin/entitlements`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { email, source: "pilot", days: 7, written_units: 0, reason: "Fixture: e2e pilot access" },
  });
  expect(grant.status()).toBe(201);

  await onboardBiologyXI(learner);
  await startTest(learner, 2);
  await answer(learner, true);
  await expect(learner.getByRole("status").first()).toHaveText(/1 answered · all saved/, AUTH);
  await learner.goto("/account");
  await expect(learner.getByText(/Pilot access until/)).toBeVisible(AUTH);
  const own = (await learner.context().cookies()).find((c) => c.name === "portal_session")!.value;
  const access = await (await request.get(`${API}/v1/me/access`, { headers: { Authorization: `Bearer ${own}` } })).json();
  expect(access.trial.status).toBe("available"); // the free trial is still unused
  // On another device the same access applies and the test is waiting.
  const phone = await signInElsewhere(browser, email);
  await expect(phone.getByRole("region", { name: "Unfinished tests" })).toContainText("1 of 2 answered", AUTH);
});
