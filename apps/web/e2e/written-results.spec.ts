import { expect, test, type Browser, type Page } from "@playwright/test";

// Written results as the learner sees them. Technical fixture question and labelled dev-seed staff only.
// * W02.S1.T3 (COMPLETENESS-01, §20.9.3): when a teacher finds that none of a script's questions can be assessed, the
//   learner sees that the test has no mark (not a zero), why, and that the allowance came back.
// * W07.S2.T2 (HISTORY-01): after a recheck, the mark history shows each version, the marking guide it used, and why
//   a question's mark changed.
const AUTH = { timeout: 20_000 };
const PASSWORD = "studio-fixture-pass-1"; // pragma: allowlist secret (dev-seed fixture, refused outside development/test)

test.skip(({ isMobile }) => isMobile, "Staff journeys run on desktop");

async function teacher(browser: Browser, email = "studio-reviewer@example.com"): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`/signin?next=${encodeURIComponent("/studio/marking")}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/studio\/marking$/, AUTH);
  return page;
}

/** A new learner submits a written test on the first Class XI Biology chapter; returns the attempt id. */
async function submitScript(page: Page, label: string): Promise<string> {
  await page.goto("/signin?next=/practice?grade=11%26subject=biology");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(`e2e-${label}-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("practice-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\?/, AUTH);
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);

  await page.goto("/practice/written?grade=11&subject=biology");
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Start written test" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\/written\/[0-9a-f-]{36}$/, AUTH);
  const attemptId = page.url().split("/").pop()!;
  await page.getByLabel("Add photos or a PDF").setInputFiles("e2e/fixtures/synthetic-page.png");
  await expect(page.getByRole("list", { name: "Uploaded pages" }).getByText(/Page 1 ·/)).toBeVisible(AUTH);
  const parts = page.getByRole("group", { name: /^Question \d/ });
  for (let i = 0; i < (await parts.count()); i++) await parts.nth(i).getByLabel("Page 1").check();
  await expect(page.getByRole("status").filter({ hasText: /Saved · revision \d+/ })).toBeVisible(AUTH);
  await page.getByRole("button", { name: "Submit for marking" }).click();
  await expect(page.getByText("Waiting for a teacher")).toBeVisible(AUTH);
  return attemptId;
}

async function openScript(marker: Page, attemptId: string) {
  await marker.goto("/studio/marking");
  await marker.getByRole("link", { name: `Script ${attemptId.slice(0, 8)}` }).click();
  await marker.getByRole("button", { name: "Start marking" }).click();
}

test("a script where nothing could be assessed shows no mark, with the reason", async ({ page, browser }) => {
  test.slow();
  const attemptId = await submitScript(page, "unassessable");

  const marker = await teacher(browser);
  await openScript(marker, attemptId);
  const outcomes = marker.getByRole("combobox", { name: /^Outcome for question \d+$/ });
  await expect(outcomes.first()).toBeEnabled(AUTH);
  const count = await outcomes.count();
  for (let i = 0; i < count; i++) {
    const outcome = outcomes.nth(i);
    const position = (await outcome.getAttribute("aria-label"))!.replace("Outcome for question ", "");
    await outcome.selectOption("unavailable");
    await marker.getByLabel(`Reason for question ${position}`).fill("Fixture: the notation can't be read by any available teacher.");
  }
  await marker.getByRole("button", { name: "Release result" }).click();
  await expect(marker.getByText("Result released")).toBeVisible(AUTH);

  await page.reload();
  await expect(page.getByText("No mark for this test")).toBeVisible(AUTH);
  await expect(page.getByText(/None of the questions could be assessed, so this test has no mark/)).toBeVisible();
  await expect(page.getByText(/notation can't be read by any available teacher/).first()).toBeVisible();
  await expect(page.getByText(/\b0 \/ \d/)).toHaveCount(0); // never shown as a zero mark
});

test("a recheck appears in the mark history with its reason", async ({ page, browser }) => {
  test.slow();
  const attemptId = await submitScript(page, "history");

  const first = await teacher(browser);
  await openScript(first, attemptId);
  await first.getByRole("radiogroup", { name: "Award for a1" }).getByLabel("1", { exact: true }).check();
  await first.getByLabel("Reason for a1").fill("Fixture: first marking.");
  await first.getByRole("button", { name: "Release result" }).click();
  await expect(first.getByText("Result released")).toBeVisible(AUTH);

  await page.reload();
  await page.getByText("Ask for a recheck").click();
  await page.getByRole("group", { name: "Which questions?" }).getByLabel("Question 1").check();
  await page.getByLabel("Why should it be marked again?").fill("Fixture: I think part (a) deserves more credit.");
  await page.getByRole("button", { name: "Request recheck" }).click();
  await expect(page.getByText("Recheck requested")).toBeVisible(AUTH);

  const second = await teacher(browser, "studio-reviewer2@example.com"); // a different teacher marks the recheck
  await openScript(second, attemptId);
  await second.getByRole("radiogroup", { name: "Award for a1" }).getByLabel("2", { exact: true }).check();
  await second.getByLabel("Reason for a1").fill("Fixture: recheck marking.");
  await second.getByRole("button", { name: "Release result" }).click();
  await expect(second.getByText("Result released")).toBeVisible(AUTH);

  await page.reload();
  await expect(page.getByText("Mark history")).toBeVisible(AUTH);
  await expect(page.getByText(/^Version 1: 1 · first marking · marking guide v\d+ · released/)).toBeVisible();
  await expect(page.getByText(/^Version 2: 2 · after recheck · marking guide v\d+ · released/)).toBeVisible();
  await expect(page.getByText("Question 1: 1 → 2 — Marked again by a different teacher after your recheck request.")).toBeVisible();
});
