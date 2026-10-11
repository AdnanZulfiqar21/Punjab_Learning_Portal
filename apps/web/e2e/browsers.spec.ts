import { expect, test } from "@playwright/test";

// P19.S2.T1 (BROWSERS-01): the core journeys in every supported engine — Chromium (Chrome, Edge), Firefox and WebKit
// (Safari, and iPhone browsers, which all use WebKit) — with keyboard-only checks. The supported range and known limits
// are recorded in docs/project/SUPPORTED_BROWSERS.md. Development fixtures only.
const AUTH = { timeout: 20_000 };

test("browse to a chapter and read a free preview lesson", async ({ page }) => {
  await page.goto("/learn");
  await page.getByRole("region", { name: "Class XI", exact: true }).getByRole("link", { name: /Biology/ }).click();
  await expect(page).toHaveURL(/\/learn\/11\/biology$/, AUTH);
  await page.getByRole("link", { name: /Chapter 1(?!\d)/ }).first().click();
  const lessons = page.getByRole("region", { name: "Lessons" });
  await expect(lessons.getByText("Technical fixture preview lesson text.")).toBeVisible(AUTH);
  const img = lessons.getByRole("img", { name: "A synthetic fixture image with a box and a label" });
  await img.scrollIntoViewIfNeeded();
  await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0), AUTH).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
});

test("keyboard: the skip link reaches the content, and sign-up works without a mouse", async ({ page, browserName, isMobile }) => {
  test.skip(isMobile, "Touch devices have no Tab key");
  await page.goto("/signin?next=/practice?grade=11%26subject=biology");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  // WebKit only tabs to links when the platform's "tab to all controls" setting is on (Safari's default is off).
  if (browserName !== "webkit") {
    await expect(skip).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#main$/);
  }
  await page.getByRole("button", { name: "New here? Create an account" }).focus();
  await page.keyboard.press("Enter");
  await page.getByLabel("Email").focus();
  await page.keyboard.type(`e2e-browsers-${browserName}-${Date.now()}@example.com`);
  await page.getByLabel("Password").focus();
  await page.keyboard.type("browsers-fixture-pass-1");
  await page.keyboard.press("Enter"); // submits the form
  await expect(page).toHaveURL(/:\d+\/practice\?/, AUTH);
});

test("practice: start a test, answer by keyboard where available, and submit", async ({ page, browserName, isMobile }) => {
  test.setTimeout(90_000);
  await page.goto("/signin?next=/practice?grade=11%26subject=biology");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(`e2e-browsers-practice-${browserName}-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("browsers-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\?/, AUTH);
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByLabel("Questions", { exact: true }).fill("2");
  await page.getByRole("button", { name: "Start test" }).click();
  await expect(page.getByRole("heading", { name: "Question 1 of 2" })).toBeVisible(AUTH);
  const first = page.getByRole("group", { name: /Options for question 1/ }).getByRole("radio").first();
  if (isMobile) {
    await first.check();
  } else {
    await first.focus();
    await page.keyboard.press("Space"); // a native radio: selectable from the keyboard in every engine
  }
  await expect(first).toBeChecked();
  await expect(page.getByText("1 answered · all saved")).toBeVisible(AUTH);
  await page.getByRole("button", { name: "Finish test" }).click();
  await page.getByRole("dialog", { name: "Submit your test?" }).getByRole("button", { name: "Submit" }).click();
  await expect(page).toHaveURL(/\/result$/, AUTH);
  await expect(page.getByText("1 of 2 answered · submitted by you")).toBeVisible(AUTH);
});
