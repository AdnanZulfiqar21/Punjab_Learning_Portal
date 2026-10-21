import { expect, test } from "@playwright/test";

// W03.S2.T2 (REGION-MAP-01): one photographed page holds the answers to two parts. Submitting is held until the page's
// numbering is clear: marking each part's area (here by keyboard-friendly preset buttons) settles it, the areas are
// shown over the page, and the script is then submitted. Technical fixture question and a labelled fixture account only.
const AUTH = { timeout: 20_000 };
const PASSWORD = "practice-fixture-pass-1"; // pragma: allowlist secret (fixture learner, development/test only)

test("a page shared by two parts is submitted once each part's area is marked", async ({ page }) => {
  test.slow();
  const email = `e2e-areas-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
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
  await page.getByLabel("Add photos or a PDF").setInputFiles("e2e/fixtures/synthetic-page.png");
  await expect(page.getByRole("list", { name: "Uploaded pages" }).getByText(/Page 1 ·/)).toBeVisible(AUTH);

  const parts = page.getByRole("group", { name: /^Question \d/ });
  const count = await parts.count();
  test.skip(count < 2, "the fixture question has a single part");
  for (let i = 0; i < count; i++) await parts.nth(i).getByLabel("Page 1").check();
  await expect(page.getByRole("group", { name: "Pages with more than one answer" })).toBeVisible(AUTH);
  const submit = page.getByRole("button", { name: "Submit for marking" });
  await expect(submit).toBeDisabled();

  // Mark each part's area: the first part on the top half, every other part on the bottom half.
  for (let i = 0; i < count; i++) {
    await parts.nth(i).getByRole("button", { name: "Mark where it is on page 1" }).click();
    const picker = page.getByRole("group", { name: /^Mark the area of .* on Page 1$/ });
    await picker.getByRole("button", { name: i === 0 ? "Top half" : "Bottom half" }).click();
    await picker.getByRole("button", { name: "Save this area" }).click();
    await expect(parts.nth(i).getByText("Page 1: an area is marked")).toBeVisible(AUTH);
  }
  await expect(page.getByRole("group", { name: "Pages with more than one answer" })).toHaveCount(0);
  await expect(page.getByRole("status").filter({ hasText: /Saved · revision \d+/ })).toBeVisible(AUTH);

  await submit.click();
  await expect(page.getByText(/^Receipt [0-9a-f]{8} ·/)).toBeVisible(AUTH);
});
