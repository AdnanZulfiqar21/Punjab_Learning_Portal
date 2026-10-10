import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test, type Browser, type Page } from "@playwright/test";

// W06.S2.T3 (PR #34 review W06-10): a rubric correction applied to submitted work, end to end. Development cannot
// publish content through the editorial workflow (publication rights stay unverified), so the dev-only command
// `portal-dev-fixture-rubric-correction` sets up an isolated fixture question and publishes the corrected rubric.
// Everything else runs through the real UI and API: an MFA adjudicator selects the versions, previews and approves
// the correction, applies it (a durable job run by `portal-written-worker`, which must be running), a conflicting
// second correction is refused until it names the one it replaces, re-applying is idempotent, an independent teacher
// re-marks under the corrected rubric, and the learner sees the notice, the new marks and the history.
const AUTH = { timeout: 20_000 };
const JOB = { timeout: 60_000 };
const PASSWORD = "studio-fixture-pass-1"; // pragma: allowlist secret (dev-seed fixture, refused outside development/test)
const API_DIR = path.resolve(__dirname, "..", "..", "api");

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile, "Staff journeys run on desktop");

function fixture(...args: string[]): Record<string, string> {
  const out = execFileSync("uv", ["run", "portal-dev-fixture-rubric-correction", ...args], { cwd: API_DIR, encoding: "utf8" });
  return JSON.parse(out.trim().split("\n").at(-1)!);
}

async function staff(browser: Browser, email: string, next: string, mfa = false): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`/signin?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  if (mfa) await page.getByLabel(/Simulate a multi-factor sign-in/).check();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`:\\d+${next.replace(/[?]/g, "\\?")}$`), AUTH);
  return page;
}

test("an adjudicator applies a rubric correction; a teacher re-marks; the learner is told", async ({ page, browser }) => {
  test.slow();
  const fx = fixture("setup");

  // A learner submits a written test on the fixture question.
  const email = `e2e-adj-${Date.now()}@example.com`;
  await page.goto("/signin?next=/practice?grade=11%26subject=biology");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("practice-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\?/, AUTH);
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);
  await page.goto("/practice/written?grade=11&subject=biology");
  await page.locator(`input[name="chapter_ids"][value="${fx.chapter_id}"]`).check();
  await page.getByRole("button", { name: "Start written test" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\/written\/[0-9a-f-]{36}$/, AUTH);
  const attemptId = page.url().split("/").pop()!;
  await page.getByLabel("Add photos or a PDF").setInputFiles("e2e/fixtures/synthetic-page.png");
  await expect(page.getByRole("list", { name: "Uploaded pages" }).getByText(/Page 1 ·/)).toBeVisible(AUTH);
  await page.getByRole("group", { name: /Question 1 \(a\)/ }).getByLabel("Page 1").check();
  await page.getByRole("group", { name: /Question 1 \(b\)/ }).getByLabel("Page 1").check();
  await expect(page.getByRole("status").filter({ hasText: /Saved · revision \d+/ })).toBeVisible(AUTH);
  await page.getByRole("button", { name: "Submit for marking" }).click();
  await expect(page.getByText("Waiting for a teacher")).toBeVisible(AUTH);

  // A teacher marks it under the original rubric.
  const teacher = await staff(browser, "studio-reviewer@example.com", "/studio/marking");
  await teacher.getByRole("link", { name: `Script ${attemptId.slice(0, 8)}` }).click();
  await teacher.getByRole("button", { name: "Start marking" }).click();
  await teacher.getByRole("radiogroup", { name: "Award for a1" }).getByLabel("1", { exact: true }).check();
  await teacher.getByLabel("Reason for a1").fill("Fixture: first marking.");
  await teacher.getByRole("button", { name: "Release result" }).click();
  await expect(teacher.getByText("Result released")).toBeVisible(AUTH);

  // The rubric is corrected (published version 2 changes what earns credit in a1).
  fixture("correct", fx.rubric_item_id, "--kind", "scoring");

  // An adjudicator without an MFA session can read but not apply.
  const plain = await staff(browser, "studio-adjudicator@example.com", "/studio");
  await plain.goto(`/studio/adjudications/new?rubric=${fx.rubric_item_id}`);
  await plain.getByLabel("Why does this correction apply to work already marked?").fill("Fixture: the published guide misdescribed a1.");
  await plain.getByRole("button", { name: "Approve the correction" }).click();
  await expect(plain.getByRole("alert").filter({ hasText: "multi-factor" })).toBeVisible(AUTH);

  // With MFA: choose the source version, see the chain and impact, approve, apply.
  const adj = await staff(browser, "studio-adjudicator@example.com", "/studio", true);
  await adj.goto(`/studio/items/${fx.rubric_item_id}`);
  await adj.getByRole("link", { name: "Apply this published correction to work already marked" }).click();
  const v1 = adj.getByRole("checkbox", { name: /Version 1 → version 2/ });
  await expect(v1).toBeChecked();
  await expect(adj.getByText(/scoring changed \(a1 changed\) — teachers re-mark · 1 submitted script/)).toBeVisible();
  await adj.getByLabel("Why does this correction apply to work already marked?").fill("Fixture: the published guide misdescribed a1.");
  await adj.getByRole("button", { name: "Approve the correction" }).click();
  await expect(adj).toHaveURL(/\/studio\/adjudications\/[0-9a-f-]{36}$/, AUTH);
  const correctionUrl = adj.url();
  const progress = adj.getByRole("definition").filter({ hasText: /^\d+$/ });
  await expect(adj.getByLabel("Correction progress")).toContainText("Remaining");
  await expect(progress.nth(1)).toHaveText("1"); // remaining before applying
  await adj.getByRole("button", { name: "Apply to submitted scripts" }).click();
  await expect(adj.getByRole("status")).toContainText("Finished: 1 processed (1 regraded, 0 unaffected), 0 failed, 0 remaining", JOB);
  await adj.reload();
  await expect(adj.getByText("1 question(s) sent to a teacher to re-mark")).toBeVisible(AUTH);
  await expect(adj.getByRole("list", { name: "Processed scripts" })).toContainText(`Script ${attemptId.slice(0, 8)} · Q1 sent to a teacher to re-mark`);

  // Re-applying is idempotent: nothing more to do, no second regrade.
  await adj.getByRole("button", { name: "Apply to submitted scripts" }).click();
  await expect(adj.getByRole("status")).toContainText("Finished: 0 processed", JOB);

  // A second correction claiming the same version is refused until it names the one it replaces.
  await adj.goto(`/studio/adjudications/new?rubric=${fx.rubric_item_id}`);
  await expect(adj.getByText("Already covered by an active correction")).toBeVisible(AUTH);
  // The replace option says which correction it is: versions, approval time and reason (not just an id).
  await expect(adj.getByText(/Replace the correction for version 1 → 2 · approved .* · “Fixture: the published guide misdescribed a1\.”/)).toBeVisible();
  await adj.getByLabel("Why does this correction apply to work already marked?").fill("Fixture: a competing correction for the same version.");
  await adj.getByRole("button", { name: "Approve the correction" }).click();
  await expect(adj.getByRole("alert").filter({ hasText: "name each one you replace" })).toBeVisible(AUTH);

  // The learner is told before the re-mark, and current marks stand.
  await page.reload();
  await expect(page.getByText("Marking guide corrected")).toBeVisible(AUTH);
  await expect(page.getByText(/question 1 is waiting to be re-marked under a corrected marking guide/)).toBeVisible();
  await expect(page.getByText("Question 1: 1 / 5")).toBeVisible();

  // An independent teacher re-marks under the corrected rubric.
  await teacher.goto("/studio/marking");
  await teacher.getByRole("listitem").filter({ hasText: `Script ${attemptId.slice(0, 8)}` }).filter({ hasText: "Regrade" }).getByRole("link").click();
  await expect(teacher.getByText("Re-mark question 1 under the corrected rubric")).toBeVisible(AUTH);
  await expect(teacher.getByText(/Fixture criterion for part a, corrected/)).toBeVisible();
  await teacher.getByRole("button", { name: "Start marking" }).click();
  await teacher.getByRole("radiogroup", { name: "Award for a1" }).getByLabel("2", { exact: true }).check();
  await teacher.getByLabel("Reason for a1").fill("Fixture: re-marked under the corrected guide.");
  await teacher.getByRole("button", { name: "Release result" }).click();
  await expect(teacher.getByText("Result released")).toBeVisible(AUTH);

  await page.reload();
  await expect(page.getByText("Question 1: 2 / 5")).toBeVisible(AUTH);
  await expect(page.getByText(/after a marking-guide correction/)).toBeVisible();
  await expect(page.getByText(/waiting to be re-marked/)).toHaveCount(0);
  await adj.goto(correctionUrl);
  await expect(adj.getByLabel("Correction progress")).toContainText("Processed");
});
