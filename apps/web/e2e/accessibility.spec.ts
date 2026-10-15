import { expect, test } from "@playwright/test";
import { audit } from "./helpers/a11y";

// P19 accessibility (A11Y-01): automated WCAG 2 A/AA checks with axe on the main learner pages, signed out and in.
// Serious and critical violations fail the build. Automated rules cover only part of WCAG; manual screen-reader and
// keyboard reviews are still required before release.
const AUTH = { timeout: 20_000 };

test.describe.configure({ mode: "serial" });

test("a signed-out visit to a new help request goes to sign-in, not round in circles", async ({ page }) => {
  await page.goto("/help/new?category=account");
  await expect(page).toHaveURL(/\/signin\?next=%2Fhelp%2Fnew%3Fcategory%3Daccount$/, AUTH);
});

// The first Class XI Biology chapter (stable catalogue ID) carries the structured-blocks fixture lesson (P07.S1.T1).
for (const path of ["/", "/learn", "/learn/chapter/317f2726-31a1-55f5-bd13-a955154033e2", "/search?q=cell", "/help", "/signin"]) {
  test(`signed out: ${path} has no serious accessibility violations`, async ({ page }) => {
    await audit(page, path);
  });
}

test("signed in: dashboard, practice, help and account have no serious accessibility violations", async ({ page }) => {
  test.setTimeout(120_000);
  const email = `e2e-a11y-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  await page.goto("/signin?next=/account");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("a11y-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/account$/, AUTH);
  // P11.S1.T2 (DASHBOARD-01): a signed-in learner's home is their dashboard, with the three meters kept separate.
  await audit(page, "/");
  await expect(page.getByRole("heading", { level: 1, name: "Your dashboard" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 3 })).toHaveText(["Syllabus coverage", "Content completed", "Demonstrated knowledge"]);
  for (const path of ["/account", "/practice", "/study", "/help", "/help/new", "/notifications"]) {
    await audit(page, path);
    expect(new URL(page.url()).pathname, `${path} should not redirect a signed-in learner`).toBe(path);
  }
});

test("staff: studio, import, overview, sources, assets, lectures and support have no serious accessibility violations", async ({ page, isMobile }) => {
  test.skip(isMobile, "Staff studio runs on desktop");
  test.setTimeout(150_000);
  for (const [email, paths] of [
    ["studio-author@example.com", ["/studio", "/studio/new", "/studio/imports", "/studio/overview", "/studio/sources", "/studio/assets", "/studio/lectures"]],
    ["studio-support@example.com", ["/studio/support", "/studio/support/learners"]],
    // ACADEMIC-REVIEW-01, REVIEWER-QUALITY-01, and W06.S1.T3 (CALIBRATION-01): the calibration screen as adjudicators see it.
    ["studio-adjudicator@example.com", ["/studio/academic-reviews", "/studio/adjudications", "/studio/reviewer-quality", "/studio/calibration"]],
    ["studio-reviewer@example.com", ["/studio/marking"]], // the teacher's marking queue
  ] as const) {
    await page.context().clearCookies();
    await page.goto("/signin?next=/account");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("studio-fixture-pass-1");
    await page.getByLabel(/Simulate a multi-factor sign-in/).check();
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page).toHaveURL(/:\d+\/account$/, AUTH);
    for (const path of paths) {
      await audit(page, path);
      expect(new URL(page.url()).pathname, `${path} should not redirect signed-in staff`).toBe(path);
    }
  }
});
