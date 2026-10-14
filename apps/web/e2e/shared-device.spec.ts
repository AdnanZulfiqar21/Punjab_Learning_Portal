import { expect, test, type Page } from "@playwright/test";

// P19.S3.T3 (ISOLATION-01): two people on one browser. Signing out leaves nothing of the first person in the tab, its
// history or the browser's storage, and an unsent note draft stays with its own account even when a session simply
// ends. Fresh technical-fixture accounts and the labelled fixture lesson from `portal-dev-seed-practice`; no real data.
const AUTH = { timeout: 20_000 };
const LESSON = "[FIXTURE] Structured blocks lesson";
const DRAFT = "Fixture draft: written on a shared browser, never sent.";

async function register(page: Page, tag: string): Promise<string> {
  const email = `e2e-${tag}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  await page.goto("/signin?next=/account");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("isolation-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/(account|onboarding)/, AUTH);
  return email;
}

async function openLesson(page: Page) {
  await page.goto("/learn");
  await page.getByRole("region", { name: "Class XI", exact: true }).getByRole("link", { name: /Biology/ }).click();
  await expect(page).toHaveURL(/\/learn\/11\/biology$/, AUTH);
  await page.getByRole("link", { name: /Chapter 1(?!\d)/ }).first().click();
  const lesson = page.getByRole("region", { name: "Lessons" }).getByRole("article", { name: LESSON });
  await expect(lesson).toBeVisible(AUTH);
  return lesson;
}

async function writeUnsentDraft(page: Page) {
  const lesson = await openLesson(page);
  await lesson.getByRole("button", { name: "Add a private note" }).click();
  await lesson.getByLabel("My private note").fill(DRAFT);
  // Kept on this device until sent (STUDY-TOOLS-01), filed under the account.
  await expect
    .poll(() => page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("portal-note-draft:")).length))
    .toBe(1);
}

const textareas = (page: Page) => page.evaluate(() => [...document.querySelectorAll("textarea")].map((t) => t.value));

test.skip(({ isMobile }) => isMobile && !process.env.E2E_FULL_MATRIX, "Shared-device journeys run on desktop");

test("signing out leaves nothing of the last person in the tab, its history or the browser's storage", async ({ page }) => {
  const first = await register(page, "shared-first");
  await writeUnsentDraft(page);
  await page.goto("/account");
  await expect(page.getByText(first)).toBeVisible(AUTH);

  const signOut = page.waitForResponse((r) => r.url().endsWith("/account/sign-out"));
  await page.getByRole("button", { name: "Sign out of this device" }).click();
  const res = await signOut;
  expect(res.status()).toBe(303);
  expect((await res.allHeaders())["clear-site-data"]).toBe('"cache", "storage"'); // headers() hides security headers
  await expect(page).toHaveURL(/:\d+\/$/, AUTH);
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  // A full page load: no earlier page is kept hidden in the document, and no form still holds the draft.
  await expect(page.locator("body")).not.toContainText(first);
  expect(await textareas(page)).not.toContain(DRAFT);

  await page.goBack(); // the account page from history: fetched again, so it asks for a sign-in
  await expect(page).toHaveURL(/\/signin/, AUTH);
  await expect(page.locator("body")).not.toContainText(first);

  await register(page, "shared-next");
  const lesson = await openLesson(page);
  await expect(lesson.getByRole("button", { name: "Add a private note" })).toBeVisible();
  await lesson.getByRole("button", { name: "Add a private note" }).click();
  await expect(lesson.getByLabel("My private note")).toHaveValue("");
});

test("an unsent draft stays with its account when a session ends without signing out", async ({ page, context }) => {
  await register(page, "ended-first");
  await writeUnsentDraft(page);
  await context.clearCookies(); // the session ended (expired, or revoked from another device); storage is untouched

  await register(page, "ended-next");
  const lesson = await openLesson(page);
  await expect(lesson.getByRole("button", { name: "Add a private note" })).toBeVisible();
  expect(await textareas(page)).not.toContain(DRAFT);
  // The first account's draft is still on this browser, filed under that account only, for when they come back.
  expect(await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("portal-note-draft:")).length)).toBe(1);
});
