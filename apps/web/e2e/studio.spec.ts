import { expect, test, type Browser, type Page } from "@playwright/test";

// Staff studio journeys (P06) using the development fixtures from `portal-dev-seed-staff` (Class XI Biology scope).
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
  await page.getByLabel("Book").selectOption({ label: "Class XI Biology" });
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
  await a.getByLabel("Book").selectOption({ label: "Class XI Biology" });
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
  await author.getByLabel("Book").selectOption({ label: "Class XI Biology" });
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
  await expect(reviewer.getByText("KEY")).toBeVisible(); // staff preview shows the key; learners never receive it
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
