import { expect, test, type Browser, type Page } from "@playwright/test";

// Help requests, question reports and the staff support queue (P15.S3) with the development fixtures from
// `portal-dev-seed-staff` and `portal-dev-seed-practice`. Every question here is a technical fixture.
const AUTH = { timeout: 20_000 };

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile, "Support journeys run on desktop");

async function newLearner(page: Page, next: string): Promise<string> {
  const email = `e2e-support-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  await page.goto(`/signin?next=${encodeURIComponent(next)}`);
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("support-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(new RegExp(`:\\d+${next.replace(/[?]/g, "\\?")}`), AUTH);
  return email;
}

async function staff(browser: Browser, email: string, path: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`/signin?next=${encodeURIComponent(path)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("studio-fixture-pass-1");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`:\\d+${path}$`), AUTH);
  return page;
}

test("a learner asks for help, staff reply, and internal notes stay internal", async ({ page, browser }) => {
  const email = await newLearner(page, "/help");
  await expect(page.getByText("No requests yet")).toBeVisible(AUTH);
  await page.getByRole("link", { name: "New request" }).click();
  await page.getByLabel("What is it about?").selectOption("account");
  const subject = `Fixture: can't change my email ${Date.now()}`;
  await page.getByLabel("Summary").fill(subject);
  await page.getByLabel("Details").fill("Fixture request body for an end-to-end test.");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page).toHaveURL(/:\d+\/help\/[0-9a-f-]{36}$/, AUTH);
  await expect(page.getByRole("heading", { name: subject })).toBeVisible();
  await expect(page.getByText("Waiting for us")).toBeVisible();

  const agent = await staff(browser, "studio-support@example.com", "/studio/support");
  await agent.getByRole("link", { name: subject }).click();
  await expect(agent.getByText(`Learner: ${email}`)).toBeVisible(AUTH); // support staff see minimal identity
  await agent.getByLabel("Message to the learner or note").fill("Fixture internal note: checked the audit log.");
  await agent.getByLabel(/Internal note/).check();
  await agent.getByRole("button", { name: "Add note" }).click();
  await expect(agent.getByText("Fixture internal note: checked the audit log.")).toBeVisible(AUTH);
  await expect(agent.getByLabel(/Internal note/)).not.toBeChecked(AUTH);
  await agent.getByLabel("Message to the learner or note").fill("Fixture reply: please sign out and back in.");
  await agent.getByLabel("Set status").selectOption("waiting_learner");
  await agent.getByRole("button", { name: "Send reply" }).click();
  await expect(agent.getByText("Fixture reply: please sign out and back in.")).toBeVisible(AUTH);

  await page.reload();
  await expect(page.getByText("Fixture reply: please sign out and back in.")).toBeVisible(AUTH);
  await expect(page.getByText("Waiting for your reply")).toBeVisible();
  await expect(page.getByText(/Fixture internal note/)).toHaveCount(0);
  await page.getByLabel("Add a reply").fill("Fixture: that worked, thanks.");
  await page.getByRole("button", { name: "Send reply" }).click();
  await expect(page.getByText("Fixture: that worked, thanks.")).toBeVisible(AUTH);
});

test("a question report reaches a scoped reviewer without the learner's identity", async ({ page, browser }) => {
  const email = await newLearner(page, "/practice?grade=11&subject=biology");
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByLabel("Questions", { exact: true }).fill("2");
  await page.getByRole("button", { name: "Start test" }).click();
  await expect(page).toHaveURL(/\/practice\/attempt\/[0-9a-f-]{36}$/, AUTH);
  await page.getByRole("button", { name: "Finish test" }).click();
  await page.getByRole("dialog", { name: "Submit your test?" }).getByRole("button", { name: "Submit" }).click();
  await expect(page).toHaveURL(/\/result$/, AUTH);

  await page.getByRole("link", { name: "Report a problem with question 2" }).click();
  await expect(page.getByText("You're reporting question 2 from your test.")).toBeVisible(AUTH);
  await page.getByLabel("Details").fill("Fixture report: the key looks wrong to me.");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page).toHaveURL(/:\d+\/help\/[0-9a-f-]{36}$/, AUTH);
  const ticketUrl = new URL(page.url()).pathname;
  await expect(page.getByRole("heading", { name: "Question 2 may be wrong" })).toBeVisible();

  const reviewer = await staff(browser, "studio-reviewer@example.com", "/studio/support");
  await reviewer.goto(ticketUrl.replace("/help/", "/studio/support/"));
  await expect(reviewer.getByText(/^Question:/)).toBeVisible(AUTH);
  await expect(reviewer.getByText("The learner's identity is not shown to reviewers.")).toBeVisible();
  await expect(reviewer.getByText(email)).toHaveCount(0);
});

test("support pages are for staff only", async ({ page }) => {
  await newLearner(page, "/studio/support");
  await expect(page.getByText("Staff only")).toBeVisible(AUTH);
});
