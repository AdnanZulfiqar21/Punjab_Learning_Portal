import { expect, test, type Browser, type Page } from "@playwright/test";
import { audit } from "./helpers/a11y";

// Written results as the learner sees them. Technical fixture question and labelled dev-seed staff only.
// * W02.S1.T3 (COMPLETENESS-01, §20.9.3): when a teacher finds that none of a script's questions can be assessed, the
//   learner sees that the test has no mark (not a zero), why, and that the allowance came back.
// * W07.S2.T2 (HISTORY-01): after a recheck, the mark history shows each version, the marking guide it used, and why
//   a question's mark changed.
const AUTH = { timeout: 20_000 };
const PASSWORD = "studio-fixture-pass-1"; // pragma: allowlist secret (dev-seed fixture, refused outside development/test)

test.skip(({ isMobile }) => isMobile, "Staff journeys run on desktop");

async function teacher(browser: Browser, email = "studio-reviewer@example.com", next = "/studio/marking", mfa = false): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`/signin?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  if (mfa) await page.getByLabel(/Simulate a multi-factor sign-in/).check();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`:\\d+${next}$`), AUTH);
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
  // REGION-MAP-01: page 1 answers every part, so its question numbering is confirmed before submitting.
  await page.getByLabel("I wrote the question numbers clearly on page 1").check();
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

// W01.S2.T2 / W05.S2.T3 (ACADEMIC-REVIEW-01): a method the marking guide doesn't cover waits for an academic decision.
test("a method the guide doesn't list waits for academic review, then is marked", async ({ page, browser }) => {
  test.slow();
  const attemptId = await submitScript(page, "academic");

  const marker = await teacher(browser);
  await openScript(marker, attemptId);
  // MARKING-RULES-01: the fixture guide states no rule for several final answers, so the proposed default shows, labelled.
  await marker.locator("summary", { hasText: "Marking rules" }).filter({ visible: true }).first().click();
  await expect(
    marker.getByText(/Several or contradictory final answers: This guide gives no rule .*\(proposed default: this guide states no rule\)/).filter({ visible: true }).first(),
  ).toBeVisible();
  await marker.getByLabel("Outcome for question 1").selectOption("pending");
  await marker.getByLabel("Academic review for question 1").selectOption("unlisted_method");
  await marker.getByLabel("Reason for question 1").fill("Fixture: a valid method the marking guide doesn't list.");
  await marker.getByRole("button", { name: "Release result" }).click();
  await expect(marker.getByText("Result released")).toBeVisible(AUTH);

  await page.reload();
  await expect(page.getByText(/A senior subject reviewer is checking how the marking guide applies to your answer/)).toBeVisible(AUTH);

  const adjudicator = await teacher(browser, "studio-adjudicator@example.com", "/studio/academic-reviews", true);
  const item = adjudicator.getByRole("list", { name: "Open academic reviews" }).getByRole("listitem").filter({ hasText: `Script ${attemptId.slice(0, 8)}` });
  await expect(item).toContainText("Valid method the guide doesn't list");
  await item.getByLabel("Why (kept on the record and shown to the marker)").fill("Fixture: the guide stands for this method.");
  await item.getByRole("button", { name: "Record the decision" }).click();
  const decided = adjudicator.getByRole("list", { name: "Decided academic reviews" });
  await expect(decided.getByText(`Script ${attemptId.slice(0, 8)} · question 1 · Guide stands`)).toBeVisible(AUTH);

  await openScript(marker, attemptId); // the completion case for the pending question
  await marker.getByRole("radiogroup", { name: "Award for a1" }).getByLabel("1", { exact: true }).check();
  await marker.getByLabel("Reason for a1").fill("Fixture: marked under the guide.");
  await marker.getByRole("button", { name: "Release result" }).click();
  await expect(marker.getByText("Result released")).toBeVisible(AUTH);
  await page.reload();
  await expect(page.getByText(/^Question 1: 1 \/ \d+$/)).toBeVisible(AUTH);
});

// W06.S1.T2 (CASE-HANDBACK-01): a teacher gives a script back so another can take it at once; an academic adjudicator
// (MFA) frees a script a teacher left, with a reason, and that teacher's next action is refused.
test("a teacher gives a script back, and an adjudicator frees one a teacher left", async ({ page, browser }) => {
  test.slow();
  const attemptId = await submitScript(page, "handback");

  const first = await teacher(browser);
  await openScript(first, attemptId);
  await first.getByRole("button", { name: "Give back to the queue" }).click();
  await expect(first.getByRole("button", { name: "Start marking" })).toBeEnabled(AUTH);

  const second = await teacher(browser, "studio-reviewer2@example.com");
  await openScript(second, attemptId);
  await expect(second.getByRole("button", { name: "Give back to the queue" })).toBeVisible(AUTH);

  const lead = await teacher(browser, "studio-adjudicator@example.com", "/studio/marking", true);
  await lead.getByRole("link", { name: `Script ${attemptId.slice(0, 8)}` }).click();
  await expect(lead.getByRole("heading", { level: 1, name: `Script ${attemptId.slice(0, 8)}` })).toBeVisible(AUTH);
  // Next keeps the previous page (the queue, with the same badge) in the DOM, hidden: look only at what is shown.
  await expect(lead.getByText("Another teacher is marking").filter({ visible: true })).toBeVisible(AUTH);
  const free = lead.getByRole("form", { name: "Free this script" });
  await free.getByLabel(/Why free this script/).fill("Fixture: the marker was called away");
  await audit(lead, null);
  await free.getByRole("button", { name: "Free this script" }).click();
  await expect(lead.getByRole("button", { name: "Start marking" })).toBeEnabled(AUTH);
  await expect(lead.getByRole("form", { name: "Free this script" })).toHaveCount(0);

  await second.getByRole("button", { name: "Give back to the queue" }).click(); // its screen is out of date
  await expect(second.getByRole("alert").filter({ hasText: "You aren't marking this script" })).toBeVisible(AUTH);
});
