import { readFile } from "node:fs/promises";
import { expect, test, type Browser, type Page } from "@playwright/test";
import { png, zip } from "./helpers/zip";

// Staff studio journeys (P06) using the development fixtures from `portal-dev-seed-staff` (Class 11 Biology scope).
// Lesson text here is a technical fixture. Publication rights stay UNVERIFIED in development, so nothing published
// here can reach learners; the publish attempt is expected to be blocked by the rights gate.
const PASSWORD = "studio-fixture-pass-1";
const AUTH = { timeout: 20_000 };

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile, "Staff studio journeys run on desktop");

async function signIn(browser: Browser, email: string, mfa = false): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto("/signin?next=/studio");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  if (mfa) await page.getByLabel(/Simulate a multi-factor sign-in/).check();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/studio$/, AUTH);
  return page;
}

let itemUrl = "";
let title = "";

test("the studio is for signed-in staff only", async ({ page }) => {
  await page.goto("/studio");
  await expect(page).toHaveURL(/\/signin\?next=(%2F|\/)studio$/);
  const email = `e2e-student-${Date.now()}@example.com`;
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("student-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/studio$/, AUTH);
  await expect(page.getByText("Staff only")).toBeVisible();
});

test("an author drafts with autosave and submits for review", async ({ browser }) => {
  title = `Fixture lesson ${Date.now()}`; // unique per run; later tests in this serial group use it
  const page = await signIn(browser, "studio-author@example.com");
  await page.getByRole("link", { name: "New draft" }).click();
  await page.getByLabel("Book").selectOption({ label: "Class 11 Biology" });
  await page.getByLabel("Chapter", { exact: true }).selectOption({ index: 1 });
  await page.getByLabel("Title").fill(title);
  await page.getByRole("button", { name: "Create draft" }).click();
  await expect(page).toHaveURL(/\/studio\/items\/[0-9a-f-]{36}$/, AUTH);
  itemUrl = new URL(page.url()).pathname;
  await expect(page.getByRole("heading", { name: title })).toBeVisible();

  await page.getByRole("button", { name: "+ Paragraph" }).click();
  await page.getByLabel("Paragraph text").fill("Technical fixture paragraph for the studio journey.");
  await page.getByRole("button", { name: "+ Add page reference" }).click();
  await expect(page.getByRole("status")).toHaveText(/Saved · revision \d+/, AUTH);

  // Preview renders the blocks and the source reference.
  await page.getByRole("tab", { name: "Preview" }).click();
  await expect(page.getByText("Technical fixture paragraph for the studio journey.")).toBeVisible();
  await expect(page.getByText(/Source: C11-BIO, PDF p\. \d+/)).toBeVisible();

  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page.getByText("In review · version 1")).toBeVisible(AUTH);
  await expect(page.getByRole("button", { name: "Withdraw from review" })).toBeVisible();
});

test("an independent reviewer approves; the rights gate blocks publication", async ({ browser }) => {
  // P06.S1.T2 (ASSIGN-REVIEWER-01): a publisher (MFA) assigns the review to an eligible reviewer first.
  const assigner = await signIn(browser, "studio-publisher@example.com", true);
  await assigner.goto(itemUrl);
  const assign = assigner.getByRole("region", { name: "Reviewer" });
  await assign.getByLabel("Assign to").selectOption({ label: "studio-reviewer@example.com" });
  await assign.getByRole("button", { name: "Assign" }).click();
  await expect(assign.getByText("Assigned to studio-reviewer@example.com.")).toBeVisible(AUTH);

  const reviewer = await signIn(browser, "studio-reviewer@example.com");
  await reviewer.getByRole("link", { name: title }).click();
  await expect(reviewer.getByText("In review · version 1")).toBeVisible();
  await reviewer.getByLabel("Review comment").fill("Checked against the referenced pages.");
  await reviewer.getByRole("button", { name: "Approve" }).click();
  await expect(reviewer.getByText("Approved · version 1")).toBeVisible(AUTH);
  await expect(reviewer.getByText(/Publication rights for C11-BIO are UNVERIFIED/)).toBeVisible();

  // Publishing needs an MFA session…
  const noMfa = await signIn(browser, "studio-publisher@example.com");
  await noMfa.goto(itemUrl);
  await expect(noMfa.getByRole("button", { name: "Publish to learners" })).toHaveCount(0);

  // …and confirmed publication rights, which development data never has.
  const publisher = await signIn(browser, "studio-publisher@example.com", true);
  await publisher.goto(itemUrl);
  await publisher.getByRole("button", { name: "Publish to learners" }).click();
  await expect(publisher.getByRole("alert").filter({ hasText: "can't be published yet" })).toBeVisible(AUTH);
  await expect(publisher.getByText("Approved · version 1")).toBeVisible();
  await expect(publisher.getByText("Not published")).toBeVisible();
});

test("concurrent edits never overwrite each other", async ({ browser }) => {
  const a = await signIn(browser, "studio-author@example.com");
  await a.getByRole("link", { name: "New draft" }).click();
  await a.getByLabel("Book").selectOption({ label: "Class 11 Biology" });
  await a.getByLabel("Chapter", { exact: true }).selectOption({ index: 2 });
  await a.getByLabel("Title").fill(`${title} (concurrency)`);
  await a.getByRole("button", { name: "Create draft" }).click();
  await expect(a).toHaveURL(/\/studio\/items\//, AUTH);
  const url = new URL(a.url()).pathname;

  const b = await signIn(browser, "studio-author2@example.com");
  await b.goto(url); // opened at revision 1

  await a.getByRole("button", { name: "+ Paragraph" }).click();
  await a.getByLabel("Paragraph text").fill("Author A's fixture text.");
  await expect(a.getByRole("status")).toHaveText(/Saved · revision 2/, AUTH);

  await b.getByRole("button", { name: "+ Heading" }).click();
  await b.getByLabel("Heading text").fill("Author B's fixture heading");
  const conflict = b.getByRole("alert").filter({ hasText: "Someone else saved a newer version" });
  await expect(conflict).toBeVisible(AUTH);
  await expect(conflict.getByText(/studio-author@example\.com saved revision 2/)).toBeVisible();
  await b.getByRole("button", { name: "Use their version (discard mine)" }).click();
  await b.getByRole("tab", { name: "Preview" }).click();
  await expect(b.getByText("Author A's fixture text.")).toBeVisible(AUTH);
});

test("a question needs every review check before it can be approved", async ({ browser }) => {
  const qTitle = `Fixture question ${Date.now()}`;
  const author = await signIn(browser, "studio-author@example.com");
  await author.getByRole("link", { name: "New draft" }).click();
  await author.getByLabel("Multiple-choice question").check();
  await author.getByLabel("Book").selectOption({ label: "Class 11 Biology" });
  await author.getByLabel("Chapter", { exact: true }).selectOption({ index: 1 });
  await author.getByLabel("Title").fill(qTitle);
  await author.getByRole("button", { name: "Create draft" }).click();
  await expect(author).toHaveURL(/\/studio\/items\//, AUTH);

  const stem = author.getByRole("region", { name: "Question stem" });
  await stem.getByRole("button", { name: "+ Paragraph" }).click();
  await stem.getByLabel("Paragraph text").fill("Fixture stem for the question journey.");
  const options = author.getByRole("region", { name: "Options" });
  for (const id of ["o1", "o2", "o3", "o4"]) {
    const option = options.locator("div.rounded-xl").filter({ hasText: `Option ${id}` });
    await option.getByRole("button", { name: "+ Paragraph" }).click();
    await option.getByLabel("Paragraph text").fill(`Fixture option ${id}`);
  }
  await options.getByLabel(/^Option o3/).check();
  const why = author.getByRole("region", { name: "Why the correct answer is correct" });
  await why.getByRole("button", { name: "+ Paragraph" }).first().click();
  await why.getByLabel("Paragraph text").first().fill("Fixture reasoning for option o3.");
  await author.getByRole("button", { name: "+ Add page reference" }).click();
  await expect(author.getByRole("status")).toHaveText(/Saved · revision \d+/, AUTH);
  await author.getByRole("button", { name: "Submit for review" }).click();
  await expect(author.getByText("In review · version 1")).toBeVisible(AUTH);

  const reviewer = await signIn(browser, "studio-reviewer@example.com");
  await reviewer.getByRole("link", { name: qTitle }).click();
  await reviewer.getByRole("tab", { name: "Preview" }).click();
  await expect(reviewer.getByText("KEY", { exact: true })).toBeVisible(); // staff preview shows the key; learners never receive it
  await reviewer.getByLabel("Review comment").fill("Checked the fixture against the referenced pages.");
  const approve = reviewer.getByRole("button", { name: "Approve" });
  await expect(approve).toBeDisabled();
  for (const check of ["accuracy", "ambiguity", "units", "diagrams", "grammar", "mapping"]) {
    await reviewer.getByLabel(check, { exact: true }).check();
  }
  await expect(approve).toBeEnabled();
  await approve.click();
  await expect(reviewer.getByText("Approved · version 1")).toBeVisible(AUTH);
});

test("a written question gets a rubric that must reconcile with its marks", async ({ browser }) => {
  const wTitle = `Fixture written ${Date.now()}`;
  const author = await signIn(browser, "studio-author@example.com");
  await author.getByRole("link", { name: "New draft" }).click();
  await author.getByLabel("Written question").check();
  await author.getByLabel("Book").selectOption({ label: "Class 11 Biology" });
  await author.getByLabel("Chapter", { exact: true }).selectOption({ index: 3 });
  await author.getByLabel("Title").fill(wTitle);
  await author.getByRole("button", { name: "Create draft" }).click();
  await expect(author).toHaveURL(/\/studio\/items\//, AUTH);

  await author.getByRole("region", { name: "Question" }).getByRole("button", { name: "+ Paragraph" }).click();
  await author.getByRole("region", { name: "Question" }).getByLabel("Paragraph text").fill("Fixture written stem.");
  const parts = author.getByRole("region", { name: "Subparts" });
  await parts.getByRole("button", { name: "+ Add subpart" }).click();
  await parts.getByRole("button", { name: "+ Add subpart" }).click();
  await parts.getByLabel("Marks").nth(0).fill("2");
  await parts.getByLabel("Marks").nth(1).fill("3");
  await expect(author.getByLabel("Total marks")).toHaveValue("5");
  await author.getByRole("button", { name: "+ Add page reference" }).click();
  await expect(author.getByRole("status")).toHaveText(/Saved · revision \d+/, AUTH);

  await author.getByRole("button", { name: "Add a marking rubric" }).click();
  await expect(author.getByRole("heading", { name: `Rubric: ${wTitle}` })).toBeVisible(AUTH);
  await author.getByLabel("Question version this rubric marks").selectOption({ index: 1 });
  const crit = author.getByRole("region", { name: "Criteria" });
  await crit.getByRole("button", { name: "+ Add criterion" }).click();
  await crit.getByRole("button", { name: "+ Add criterion" }).click();
  await crit.getByLabel("Slot").nth(1).selectOption({ label: "(b)" });
  await crit.getByLabel("Maximum").nth(0).fill("2");
  await crit.getByLabel(/Permitted awards/).nth(0).fill("0, 1, 2");
  await crit.getByLabel(/What earns credit/).nth(0).fill("Fixture criterion for part a");
  await crit.getByLabel("Maximum").nth(1).fill("3");
  await crit.getByLabel(/Permitted awards/).nth(1).fill("0, 1.5, 3");
  await crit.getByLabel(/What earns credit/).nth(1).fill("Fixture criterion for part b");
  const rec = author.getByRole("table", { name: "Reconciliation with the question" });
  await expect(rec.getByRole("row", { name: /\(a\)/ })).toContainText("2 ✓");
  await expect(rec.getByRole("row", { name: /\(b\)/ })).toContainText("3 ✓");
  await author.getByRole("button", { name: "+ Add page reference" }).click();
  await expect(author.getByRole("status")).toHaveText(/Saved · revision \d+/, AUTH);
  await author.getByRole("button", { name: "Submit for review" }).click();
  await expect(author.getByText("In review · version 1")).toBeVisible(AUTH);
});

test("an academic adjudicator reaches rubric corrections from the studio", async ({ browser }) => {
  // W06.S2.T3: the regrade itself is covered by API tests against real PostgreSQL (test_rubric_adjudication.py);
  // this checks the studio wiring and scope for the seeded adjudicator.
  const adjudicator = await signIn(browser, "studio-adjudicator@example.com");
  await adjudicator.getByRole("link", { name: "Rubric corrections" }).click();
  await expect(adjudicator.getByRole("heading", { name: "Rubric corrections" })).toBeVisible(AUTH);
  await expect(adjudicator.getByRole("list", { name: "Rubric corrections" }).or(adjudicator.getByText("None yet"))).toBeVisible(AUTH);
});

test("an author previews an import, sees row errors, and commits valid rows as drafts", async ({ browser }) => {
  // P06.S2: a dry-run preview writes nothing; only an error-free batch commits, and only as drafts.
  const author = await signIn(browser, "studio-author@example.com");
  await author.goto("/studio/new");
  const chapterId = await author.getByLabel("Chapter", { exact: true }).locator("option").nth(4).getAttribute("value");
  expect(chapterId).toBeTruthy();
  const run = Date.now();
  const p = (text: string) => [{ type: "paragraph", text }];
  const row = (ext: string, chapter: string) => ({
    external_id: ext,
    chapter,
    title: `Fixture import ${ext}`,
    body: {
      stem: p(`Fixture imported stem ${ext}`),
      options: ["one", "two", "three", "four"].map((w, i) => ({ id: `o${i + 1}`, blocks: p(`Fixture option ${w}`) })),
      correct_option_id: "o2",
      explanation: { correct: p("Fixture reasoning.") },
    },
    source_refs: [],
  });
  const file = (...items: unknown[]) => ({
    name: `fixture-${run}.json`,
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ schema_version: 1, kind: "mcq", items })),
  });
  await author.goto("/studio/imports");
  await author.getByLabel(/File to preview/).setInputFiles(file(row(`E2E-${run}-1`, chapterId!), row(`E2E-${run}-2`, "no-such-chapter")));
  const rows = author.getByRole("list", { name: "Import rows" });
  await expect(rows.getByText("Error")).toBeVisible(AUTH);
  await expect(author.getByRole("button", { name: /Import 1 row as drafts/ })).toBeDisabled();
  await author.getByLabel(/File to preview/).setInputFiles(file(row(`E2E-${run}-1`, chapterId!)));
  await expect(rows.getByText("New draft")).toBeVisible(AUTH);
  await author.getByRole("button", { name: "Import 1 row as drafts" }).click();
  await expect(author.getByRole("heading", { name: /^Imported:/ })).toBeVisible(AUTH);
  await rows.getByRole("link", { name: "Open" }).click();
  await expect(author.getByText(/^Draft · version 1/)).toBeVisible(AUTH);
});

test("an author downloads the Excel template, and a workbook goes through the same checks", async ({ browser }) => {
  // P06.S2.T1 (IMPORT-XLSX-01): headings-only templates; an .xlsx upload is read by the same validation as CSV.
  const author = await signIn(browser, "studio-author@example.com");
  await author.goto("/studio/imports");
  const [download] = await Promise.all([author.waitForEvent("download"), author.getByRole("link", { name: "Excel (.xlsx)" }).click()]);
  expect(download.suggestedFilename()).toBe("mcq-template.xlsx");
  const buffer = await readFile((await download.path())!);
  expect(buffer.subarray(0, 2).toString()).toBe("PK"); // a zip package, as every .xlsx is
  const csv = await author.request.get("/studio/imports/templates/mcq.csv");
  expect(csv.status()).toBe(200);
  expect((await csv.text()).replace(/^﻿/, "").startsWith("external_id,chapter,topic,title,stem")).toBe(true);
  // The template has headings and no rows, so the preview says exactly that.
  await author.getByLabel(/File to preview/).setInputFiles({ name: "mcq-template.xlsx", mimeType: "application/octet-stream", buffer });
  await expect(author.getByText("The file has no rows.")).toBeVisible(AUTH);
});

test("an author checks a media pack, archives it, and the same pack again changes nothing", async ({ browser }) => {
  // MEDIA-MANIFEST-01: preview scans and checks every file and writes nothing; the commit archives all or none.
  const author = await signIn(browser, "studio-author@example.com");
  const run = Date.now();
  const manifest = {
    schema_version: 1,
    kind: "media",
    grade: 11,
    subject: "biology",
    items: [
      {
        external_id: `e2e-fig-${run}`,
        kind: "image",
        title: `Fixture pack image ${run}`,
        file: "figures/fixture.png",
        provenance: { source: "Fixture: drawn by the browser test", licence: "Owner's own work" },
      },
    ],
  };
  const pack = zip({ "manifest.json": Buffer.from(JSON.stringify(manifest)), "figures/fixture.png": png(8, 6, [20, 90, 160]) });
  const file = { name: `fixture-pack-${run}.zip`, mimeType: "application/zip", buffer: pack };
  await author.goto("/studio/assets?grade=11&subject=biology");
  const section = author.getByRole("region", { name: "Media pack" });
  await section.getByLabel("Pack to check").setInputFiles(file);
  const files = section.getByRole("list", { name: "Pack files" });
  await expect(files.getByText("New asset")).toBeVisible(AUTH);
  await section.getByRole("button", { name: "Archive 1 file" }).click();
  await expect(section.getByText(/^Archived/)).toBeVisible(AUTH);
  await expect(files.getByText(/^Version 1: [0-9a-f-]{36}$/)).toBeVisible();
  await expect(author.getByText(`pack key e2e-fig-${run}`)).toBeVisible(AUTH); // the archive list shows it
  await section.getByLabel("Pack to check").setInputFiles(file);
  await expect(files.getByText("Unchanged")).toBeVisible(AUTH);
  await expect(section.getByRole("button", { name: /Archive/ })).toBeDisabled();
});

test("a file too big for a quick preview is checked by the import worker, with progress", async ({ browser }) => {
  // IMPORT-BULK-01: more rows than a request preview takes, so the page hands the file to the worker and follows it.
  // Every row names a chapter that doesn't exist, so the check is real but nothing is ever written.
  test.slow();
  const author = await signIn(browser, "studio-author@example.com");
  const run = Date.now();
  const header = "external_id,chapter,title,stem,option_a,option_b,correct";
  const lines = Array.from({ length: 2001 }, (_, i) => `E2E-BULK-${run}-${i},no-such-chapter-${run},Fixture,Fixture stem ${i},A,B,A`);
  await author.goto("/studio/imports");
  await author.getByLabel(/File to preview/).setInputFiles({
    name: `fixture-bulk-${run}.csv`,
    mimeType: "text/csv",
    buffer: Buffer.from([header, ...lines].join("\n") + "\n"),
  });
  await expect(author.getByRole("heading", { name: /^(Queued|Checking|Preview): fixture-bulk-/ })).toBeVisible({ timeout: 20_000 });
  await expect(author.getByRole("heading", { name: `Preview: fixture-bulk-${run}.csv` })).toBeVisible({ timeout: 90_000 });
  await expect(author.getByText("Showing the 500 rows with errors or warnings out of 2001.")).toBeVisible();
  await expect(author.getByRole("button", { name: /Import \d+ rows? as drafts/ })).toBeDisabled();
  await author.getByRole("button", { name: "Discard" }).click();
  await expect(author.getByRole("heading", { name: `Discarded: fixture-bulk-${run}.csv` })).toBeVisible(AUTH);
  // Leaving and coming back: the recent imports list reopens the batch.
  await author.goto("/studio/imports");
  const recent = author.getByRole("region", { name: "Your recent imports" });
  await recent.getByRole("link", { name: `fixture-bulk-${run}.csv` }).click();
  await expect(author.getByRole("heading", { name: `Discarded: fixture-bulk-${run}.csv` })).toBeVisible(AUTH);
});
