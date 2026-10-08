import { expect, test, type Page } from "@playwright/test";

// Lesson access (review R07): premium lessons need a plan or the free trial; previews are open to everyone. Uses the two
// labelled fixture lessons from `portal-dev-seed-practice` (Class XI Biology, first chapter). Not academic content.
const AUTH = { timeout: 20_000 };
const PREVIEW = "Technical fixture preview lesson text.";
const PREMIUM = "Technical fixture premium lesson text.";

async function openFirstBiologyChapter(page: Page) {
  await page.goto("/learn");
  await page.getByRole("region", { name: "Class XI", exact: true }).getByRole("link", { name: /Biology/ }).click();
  await expect(page).toHaveURL(/\/learn\/11\/biology$/, AUTH);
  await page.getByRole("link", { name: /Chapter 1(?!\d)/ }).first().click();
  await expect(page.getByRole("region", { name: "Lessons" })).toBeVisible(AUTH);
  return page.getByRole("region", { name: "Lessons" });
}

test.skip(({ isMobile }) => isMobile, "Lesson access journeys run on desktop");

test("anyone reads a free preview; a premium lesson shows what it is but not its text", async ({ page }) => {
  const lessons = await openFirstBiologyChapter(page);
  await expect(lessons.getByText(PREVIEW)).toBeVisible();
  await expect(lessons.getByText(/Free preview ·/)).toBeVisible();
  await expect(lessons.getByRole("heading", { name: "[FIXTURE] Premium lesson" })).toBeVisible();
  await expect(lessons.getByText("This lesson is included with a plan or the free 30-day trial.")).toBeVisible();
  await expect(lessons.getByText(PREMIUM)).toHaveCount(0);
});

test("a learner on the free trial reads premium lessons", async ({ page }) => {
  const email = `e2e-lessons-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  await page.goto("/signin?next=/account");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("lessons-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/(account|onboarding)/, AUTH);
  await page.goto("/account");
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);
  const lessons = await openFirstBiologyChapter(page);
  await expect(lessons.getByText(PREMIUM)).toBeVisible();
  await expect(lessons.getByText("This lesson is included with a plan")).toHaveCount(0);
});
