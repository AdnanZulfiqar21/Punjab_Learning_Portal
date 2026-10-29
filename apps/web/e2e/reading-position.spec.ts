import { expect, test } from "@playwright/test";

// P11.S2.T1 (LESSON-PROGRESS-01): the chapter page remembers the lesson a learner reached and offers to continue there,
// on this or another device. Technical fixture lessons (the structured-blocks fixture chapter) and a fixture account.
const AUTH = { timeout: 20_000 };
const CHAPTER = "/learn/chapter/317f2726-31a1-55f5-bd13-a955154033e2"; // Class 11 Biology chapter 1 (stable ID)

test("a chapter offers to continue at the lesson the learner reached", async ({ page, browser }) => {
  test.slow();
  const email = `e2e-reading-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  await page.goto("/signin?next=/practice?grade=11%26subject=biology");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("practice-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\?/, AUTH);
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);

  await page.goto(CHAPTER);
  const lessons = page.locator("article[aria-labelledby^='lesson-'] h3");
  await expect(lessons.first()).toBeVisible(AUTH);
  const count = await lessons.count();
  test.skip(count < 2, "The local fixture chapter needs at least two readable lessons");
  const target = lessons.nth(count - 1);
  const title = (await target.textContent())!.trim();
  // The place counts once the heading has sat in the upper half of the screen for a moment, as when reading it.
  await target.evaluate((h) => h.scrollIntoView({ block: "start" }));
  await expect.poll(() => target.evaluate((h) => h.getBoundingClientRect().top < window.innerHeight / 2)).toBe(true);
  await page.waitForTimeout(3500);

  // Another device (a fresh browser context) signed in as the same learner sees where to continue.
  const other = await (await browser.newContext()).newPage();
  await other.goto(`/signin?next=${encodeURIComponent(CHAPTER)}`);
  await other.getByLabel("Email").fill(email);
  await other.getByLabel("Password").fill("practice-fixture-pass-1");
  await other.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(other).toHaveURL(new RegExp(`:\\d+${CHAPTER}$`), AUTH);
  await expect(other.getByRole("link", { name: `Continue where you left off: ${title}` })).toBeVisible(AUTH);
});
