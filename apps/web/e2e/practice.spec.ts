import { expect, test, type Page } from "@playwright/test";

// Learner practice journeys (P09/P10) against the development fixtures from `portal-dev-seed-practice`: technical
// fixture questions in Class XI Biology, chapter 1, whose stems say which option is the key. Not academic content.
const AUTH = { timeout: 20_000 };

async function newLearner(page: Page) {
  const email = `e2e-practice-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  await page.goto("/signin?next=/practice?grade=11%26subject=biology");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("practice-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\?/, AUTH);
}

async function startTest(page: Page, count: number, feedback: "deferred" | "immediate" = "deferred", timed = false) {
  await page.goto("/practice?grade=11&subject=biology");
  const chapter = page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first();
  await chapter.check();
  await page.getByLabel("Questions", { exact: true }).fill(String(count));
  await page.getByLabel("Feedback").selectOption(feedback);
  if (timed) await page.getByLabel("Timed", { exact: true }).check();
  await page.getByRole("button", { name: "Start test" }).click();
  await expect(page).toHaveURL(/\/practice\/attempt\/[0-9a-f-]{36}$/, AUTH);
  await expect(page.getByRole("heading", { name: `Question 1 of ${count}` })).toBeVisible(AUTH);
}

/** The fixture stem names its key ("Which option is o3?"); pick that option, or a deliberately wrong one. */
async function answer(page: Page, correct: boolean) {
  const stem = await page.getByRole("region", { name: /Question \d+/ }).innerText();
  const key = /Which option is (o\d)\?/.exec(stem)![1];
  const choice = correct ? key : ["o1", "o2", "o3", "o4"].find((o) => o !== key)!;
  await page
    .getByRole("group", { name: /Options for question/ })
    .getByLabel(new RegExp(`Fixture option ${choice}$`))
    .check();
}

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile, "Practice journeys run on desktop");

test("a learner sees only reviewed-question availability and builds a test", async ({ page }) => {
  await newLearner(page);
  await page.goto("/practice?grade=11&subject=chemistry");
  await expect(page.getByText("No approved practice questions yet")).toBeVisible();
  await page.goto("/practice?grade=11&subject=biology");
  await expect(page.getByRole("group", { name: "Chapters" }).getByText(/8 questions/)).toBeVisible();
});

test("answers save durably, survive a reload and an outage, and score after submission", async ({ page, context }) => {
  await newLearner(page);
  await startTest(page, 4);
  await answer(page, true);
  await expect(page.getByRole("status").first()).toHaveText(/1 answered · all saved/, AUTH);
  await page.getByRole("button", { name: "Next →" }).click();
  await answer(page, false);
  await expect(page.getByRole("status").first()).toHaveText(/2 answered · all saved/, AUTH);

  // A reload restores saved answers from the server.
  await page.reload();
  await expect(page.getByRole("button", { name: /Question 1: saved/ })).toBeVisible(AUTH);
  await expect(page.getByRole("button", { name: /Question 2: saved/ })).toBeVisible();

  // Offline: the selection stays pending on this device and is sent when the connection returns.
  await page.getByRole("button", { name: /Question 3:/ }).click();
  await context.setOffline(true);
  await answer(page, true);
  await expect(page.getByRole("button", { name: /Question 3: pending/ })).toBeVisible(AUTH);
  await context.setOffline(false);
  await expect(page.getByRole("button", { name: /Question 3: saved/ })).toBeVisible(AUTH);

  await page.getByRole("button", { name: "Finish test" }).click();
  const dialog = page.getByRole("dialog", { name: "Submit your test?" });
  await expect(dialog).toContainText("3 answered");
  await expect(dialog).toContainText("1 not answered");
  await dialog.getByRole("button", { name: "Submit" }).click();
  await expect(page).toHaveURL(/\/result$/, AUTH);
  const attemptUrl = page.url().replace(/\/result$/, "");
  await expect(page.getByRole("heading", { name: "Your result" })).toBeVisible();
  await expect(page.getByText(/^2$/).first()).toBeVisible(); // two correct of four
  await expect(page.getByText("/ 4")).toBeVisible();
  await expect(page.getByText("3 of 4 answered · submitted by you")).toBeVisible();
  await expect(page.getByText("Correct answer").first()).toBeVisible(); // keys are released only now

  // The attempt page now shows the submitted state instead of editable questions.
  await page.goto(attemptUrl);
  await expect(page.getByRole("heading", { name: "Test submitted" })).toBeVisible(AUTH);
});

test("immediate feedback reveals one answer and locks it", async ({ page }) => {
  await newLearner(page);
  await startTest(page, 2, "immediate");
  await answer(page, true);
  await page.getByRole("button", { name: "Check answer" }).click();
  await expect(page.getByText("Correct", { exact: true })).toBeVisible(AUTH);
  for (const radio of await page.getByRole("group", { name: /Options for question 1/ }).getByRole("radio").all()) {
    await expect(radio).toBeDisabled();
  }
});

test("timed practice shows the countdown and the tolerance rule", async ({ page }) => {
  await newLearner(page);
  await page.goto("/practice?grade=11&subject=biology");
  await page.getByLabel("Timed", { exact: true }).check();
  await expect(page.getByText(/within 3 seconds after it can be rejected/)).toBeVisible();
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByLabel("Questions", { exact: true }).fill("2");
  await page.getByLabel("Minutes", { exact: true }).fill("5");
  await page.getByRole("button", { name: "Start test" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\/attempt\/[0-9a-f-]{36}$/, AUTH);
  await expect(page.getByLabel("Time remaining")).toHaveText(/^[45]:\d\d$/, AUTH);
});

test("written practice: upload a page, map it, declare a part unanswered and submit once", async ({ page }) => {
  await newLearner(page);
  await page.goto("/practice/written?grade=11&subject=biology");
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Start written test" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\/written\/[0-9a-f-]{36}$/, AUTH);
  await expect(page.getByText(/Technical fixture written question/)).toBeVisible();
  await expect(page.getByText("Upload and submit by")).toBeVisible();

  await page.getByLabel("Add photos or a PDF").setInputFiles("e2e/fixtures/synthetic-page.png");
  const uploaded = page.getByRole("list", { name: "Uploaded pages" });
  await expect(uploaded.getByText("Page 1 · uploaded, not yet submitted")).toBeVisible(AUTH);

  await page.getByRole("group", { name: /Question 1 \(a\)/ }).getByLabel("Page 1").check();
  await page.getByRole("group", { name: /Question 1 \(b\)/ }).getByLabel("I didn't answer this").check();
  await expect(page.getByRole("status").filter({ hasText: /Saved · revision \d+/ })).toBeVisible(AUTH);
  await page.getByRole("button", { name: "Submit for marking" }).click();
  await expect(page.getByText("Submitted for marking")).toBeVisible(AUTH);
  await expect(page.getByText(/1 answered, 1 marked not answered/)).toBeVisible();
  await expect(uploaded.getByText("Page 1 · submitted")).toBeVisible();
  await expect(page.getByLabel("Add photos or a PDF")).toHaveCount(0); // no edits after submission
});

test("uploads are refused from other sites", async ({ page }) => {
  await newLearner(page);
  const res = await page.request.post("/practice/written/00000000-0000-0000-0000-000000000000/upload", {
    data: "x",
    headers: { Origin: "https://evil.example" },
  });
  expect(res.status()).toBe(403);
});
