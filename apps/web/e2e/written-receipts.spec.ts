import { expect, test, type Browser } from "@playwright/test";

// W07.S3.T2: an interrupted written journey keeps one receipt. After submitting, the learner signs out, signs in again
// on another browser (a second device), and finds the same receipt and the same "waiting for a teacher" state,
// without a guessed completion time. Technical fixture question and a labelled fixture account only.
const AUTH = { timeout: 20_000 };
const PASSWORD = "practice-fixture-pass-1"; // pragma: allowlist secret (fixture learner, development/test only)

async function signIn(browser: Browser, email: string, next: string) {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`/signin?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`:\\d+${next}$`), AUTH);
  return page;
}

test("the same receipt after signing out and in again on another device", async ({ page, browser }) => {
  test.slow();
  const email = `e2e-receipt-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  await page.goto("/signin?next=/practice?grade=11%26subject=biology");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\?/, AUTH);
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);

  await page.goto("/practice/written?grade=11&subject=biology");
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Start written test" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\/written\/[0-9a-f-]{36}$/, AUTH);
  const path = new URL(page.url()).pathname;
  await page.getByLabel("Add photos or a PDF").setInputFiles("e2e/fixtures/synthetic-page.png");
  await expect(page.getByRole("list", { name: "Uploaded pages" }).getByText(/Page 1 ·/)).toBeVisible(AUTH);
  const parts = page.getByRole("group", { name: /^Question \d/ });
  for (let i = 0; i < (await parts.count()); i++) await parts.nth(i).getByLabel("Page 1").check();
  // REGION-MAP-01: page 1 answers every part, so its question numbering is confirmed before submitting.
  await page.getByLabel("I wrote the question numbers clearly on page 1").check();
  await expect(page.getByRole("status").filter({ hasText: /Saved · revision \d+/ })).toBeVisible(AUTH);
  await page.getByRole("button", { name: "Submit for marking" }).click();
  const receipt = page.getByText(/^Receipt [0-9a-f]{8} ·/);
  await expect(receipt).toBeVisible(AUTH);
  const shown = (await receipt.textContent())!.trim();

  await page.goto("/account");
  await page.getByRole("button", { name: "Sign out of this device" }).click();
  await expect(page).toHaveURL(/\/$/, AUTH);
  await page.goto(path);
  await expect(page).toHaveURL(/\/signin/, AUTH); // signed out: the script isn't shown

  const other = await signIn(browser, email, path);
  await expect(other.getByText(/^Receipt [0-9a-f]{8} ·/)).toHaveText(shown, AUTH);
  await expect(other.getByText("Waiting for a teacher")).toBeVisible();
  await expect(other.getByText(/\b(expected|estimated) (by|in)\b/i)).toHaveCount(0); // no guessed completion time
  await expect(other.getByLabel("Add photos or a PDF")).toHaveCount(0); // still submitted, nothing to redo
});
