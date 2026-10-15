import { expect, test } from "@playwright/test";
import { audit } from "./helpers/a11y";

// The operator's service overview (OPS-01, STAFFING-01, LIFECYCLE-01) with the labelled dev-seed operator account.
const AUTH = { timeout: 20_000 };
const PASSWORD = "studio-fixture-pass-1"; // pragma: allowlist secret (dev-seed fixture, refused outside development/test)

test.skip(({ isMobile }) => isMobile, "Staff screens run on desktop");

test("an operator sees the written script lifecycle with the count behind every time", async ({ page }) => {
  await page.goto("/signin?next=/admin/service");
  await page.getByLabel("Email").fill("studio-operator@example.com");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByLabel(/Simulate a multi-factor sign-in/).check();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/admin\/service$/, AUTH);
  const lifecycle = page.getByRole("region", { name: "Written scripts, last 30 days" });
  await expect(lifecycle).toBeVisible(AUTH);
  await expect(lifecycle.getByRole("list", { name: "Script outcomes" })).toContainText("Released automatically: 0");
  const table = lifecycle.getByRole("table", { name: "Lifecycle stage times" });
  for (const stage of ["Upload while writing (per page)", "Start to submission", "Waiting for a teacher", "Teacher marking (elapsed)", "Submission to result"]) {
    await expect(table.getByRole("rowheader", { name: stage })).toBeVisible();
  }
  await expect(table.getByRole("columnheader", { name: "Count" })).toBeVisible();
  await expect(lifecycle.getByText(/Not measured yet: reading: .*\(B10\)/)).toBeVisible();
  await audit(page, null);
});

// W06.S3.T2 (STAFFING-01): an operator's staffing figures decide whether new written tests can start, and the learner
// is told honestly: "Marking is full" with no room, the promised turnaround with room. The figures are put back after.
// This file runs in the staffing Playwright project, after every other project: the closed window is shared by every
// Class XI Biology written start.
test("staffing decides whether written tests start, and learners are told", async ({ page, browser, request }) => {
  test.slow();
  const API = process.env.PORTAL_API_INTERNAL_ORIGIN ?? "http://127.0.0.1:8100";
  await page.goto("/signin?next=/admin/service");
  await page.getByLabel("Email").fill("studio-operator@example.com");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByLabel(/Simulate a multi-factor sign-in/).check();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/admin\/service$/, AUTH);
  const token = (await page.context().cookies()).find((c) => c.name === "portal_session")!.value;
  const auth = { Authorization: `Bearer ${token}` };
  const rows = (await (await request.get(`${API}/v1/ops/written-backlog`, { headers: auth })).json()) as {
    grade: number;
    subject: string;
    max_open_cases: number;
    staffing: { reviewer_hours_per_week: number; fixed_hours_per_week: number; minutes_per_script: number; turnaround_days: number } | null;
  }[];
  const before = rows.find((r) => r.grade === 11 && r.subject === "biology")!;
  expect(before).toBeTruthy();

  const learner = await (await browser.newContext()).newPage();
  await learner.goto("/signin?next=/practice?grade=11%26subject=biology");
  await learner.getByRole("button", { name: "New here? Create an account" }).click();
  await learner.getByLabel("Email").fill(`e2e-staffing-${Date.now()}@example.com`);
  await learner.getByLabel("Password").fill("practice-fixture-pass-1");
  await learner.getByRole("button", { name: "Create account" }).click();
  await expect(learner).toHaveURL(/:\d+\/practice\?/, AUTH);
  await learner.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(learner.getByText(/Free trial until/)).toBeVisible(AUTH);

  const form = page.getByRole("form", { name: "Change review staffing for Class XI Biology" });
  async function save(hours: string, fixed: string, minutes: string, reason: string) {
    await form.getByLabel("Productive marking hours a week").fill(hours);
    await form.getByLabel("Fixed obligations (hours a week)").fill(fixed);
    await form.getByLabel("Teacher minutes per script").fill(minutes);
    await form.getByLabel("Promised turnaround (days)").fill("1");
    await form.getByLabel("Case limit").fill(String(Math.max(before.max_open_cases, 1000)));
    await form.getByLabel(/^Reason/).fill(reason);
    await form.getByRole("button", { name: "Save staffing" }).click();
    await expect(form.getByRole("status")).toContainText("Saved.", AUTH);
    // The status still says "Saved." from the previous save, so wait until the API holds these figures.
    await expect
      .poll(async () => {
        const now = (await (await request.get(`${API}/v1/ops/written-backlog`, { headers: auth })).json()) as typeof rows;
        return now.find((r) => r.grade === 11 && r.subject === "biology")?.staffing?.reviewer_hours_per_week;
      }, AUTH)
      .toBe(Number(hours));
  }
  try {
    await save("1", "1", "600", "Fixture: no marking time left");
    await learner.goto("/practice/written?grade=11&subject=biology");
    await expect(learner.getByText("Marking is full right now")).toBeVisible(AUTH);
    await expect(learner.getByText(/Scripts already submitted are kept and will be marked/)).toBeVisible();

    await save("400", "0", "1", "Fixture: plenty of marking time");
    await learner.reload();
    await expect(learner.getByText("Teacher marking currently takes about 1 day from when you submit.")).toBeVisible(AUTH);
    await expect(learner.getByText("Marking is full right now")).toHaveCount(0);
  } finally {
    const restore = await request.put(`${API}/v1/ops/written-capacity/11/biology`, {
      headers: auth,
      data: before.staffing
        ? { max_open_cases: before.max_open_cases, reason: "Fixture: restore staffing", staffing: before.staffing }
        : { max_open_cases: before.max_open_cases, reason: "Fixture: restore staffing", clear_staffing: true },
    });
    expect(restore.status()).toBe(200);
  }
});
