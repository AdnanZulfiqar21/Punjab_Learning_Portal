import { expect, test } from "@playwright/test";

// P11.S2.T3 (SEARCH-01): search finds published lessons. Lesson text is matched and quoted only where the learner may
// read it; anyone finds a lesson by its title. Uses the labelled fixture lessons from `portal-dev-seed-practice`
// (Class 11 Biology, first chapter). Not academic content.
const AUTH = { timeout: 20_000 };

test("a guest finds a free preview by its text, and a premium lesson only by its title", async ({ page }) => {
  await page.goto("/search?q=preview+lesson+text");
  const preview = page.getByRole("link", { name: /\[FIXTURE\] Preview lesson/ });
  await expect(preview).toContainText("Class 11 · Biology · Lesson · Free preview");
  await expect(preview.locator("mark").first()).toContainText(/preview/i);

  await page.goto("/search?q=premium+lesson");
  const premium = page.getByRole("link", { name: /\[FIXTURE\] Premium lesson/ });
  await expect(premium).toContainText("Included with a plan or the free 30-day trial. Found by its title.");
  await expect(premium.locator("mark")).toHaveCount(0);
  await expect(page.getByText("Technical fixture premium lesson text")).toHaveCount(0);

  // Opening a result goes to the lesson on its chapter page, which checks publication and access again.
  await page.goto("/search?q=preview+lesson+text");
  await page.getByRole("link", { name: /\[FIXTURE\] Preview lesson/ }).click();
  await expect(page).toHaveURL(/\/learn\/chapter\/[0-9a-f-]+#lesson-[0-9a-f-]+$/, AUTH);
  await expect(page.getByRole("heading", { name: "[FIXTURE] Preview lesson" })).toBeVisible(AUTH);
});

test("a learner on the free trial finds premium lesson text", async ({ page, isMobile }) => {
  test.skip(isMobile && !process.env.E2E_FULL_MATRIX, "The account journey runs on desktop");
  const email = `e2e-search-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  await page.goto("/signin?next=/account");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("search-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/(account|onboarding)/, AUTH);
  await page.goto("/account");
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);

  await page.goto("/search?q=premium+lesson+text&grade=11&subject=biology");
  const premium = page.getByRole("link", { name: /\[FIXTURE\] Premium lesson/ });
  await expect(premium.locator("mark").first()).toContainText(/premium/i, AUTH);
  await expect(premium).not.toContainText("Included with a plan");
  // Filters narrow results: Class 12 has no Class 11 lesson.
  await page.goto("/search?q=premium+lesson+text&grade=12");
  await expect(page.getByRole("link", { name: /\[FIXTURE\] Premium lesson/ })).toHaveCount(0);
});
