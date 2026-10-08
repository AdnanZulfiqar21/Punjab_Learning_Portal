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
  // New learners start the one-time free trial before practising (P14.S5).
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);
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

test("practice needs a plan, and the free trial is offered once", async ({ page }) => {
  const email = `e2e-trial-${Date.now()}@example.com`;
  await page.goto("/signin?next=/practice");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("practice-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("Practice tests needs a plan")).toBeVisible(AUTH);
  await expect(page.getByText(/doesn't ask for payment details/)).toBeVisible();
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);
  await page.goto("/account");
  await expect(page.getByRole("region", { name: "Your plan" })).toContainText(/Free trial until .* Written marking allowance: 10 of 10 units left/);
});

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

test("a PDF becomes one page per PDF page, and each page maps on its own", async ({ page }) => {
  await newLearner(page);
  await page.goto("/practice/written?grade=11&subject=biology");
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Start written test" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\/written\/[0-9a-f-]{36}$/, AUTH);
  await page.getByLabel("Add photos or a PDF").setInputFiles("e2e/fixtures/synthetic-3-pages.pdf");
  const uploaded = page.getByRole("list", { name: "Uploaded pages" });
  await expect(uploaded.getByText("PDF page 3 of 3")).toBeVisible(AUTH);
  await expect(uploaded.getByRole("img")).toHaveCount(3); // every page is shown as its validated preview
  await page.getByRole("group", { name: /Question 1 \(a\)/ }).getByLabel("Page 2").check();
  await page.getByRole("group", { name: /Question 1 \(b\)/ }).getByLabel("Page 3").check();
  await expect(page.getByRole("status").filter({ hasText: /Saved · revision \d+/ })).toBeVisible(AUTH);
  await page.getByRole("button", { name: "Submit for marking" }).click();
  await expect(page.getByText("Submitted for marking")).toBeVisible(AUTH);
  await expect(page.getByText(/2 answered, 0 marked not answered/)).toBeVisible();
});

test("a pending question shows no invented mark, and a completion case finishes it", async ({ page, browser }) => {
  test.slow(); // two marking rounds across two browser contexts
  await newLearner(page);
  await page.goto("/practice/written?grade=11&subject=biology");
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
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

  const teacher = await (await browser.newContext()).newPage();
  await teacher.goto("/signin?next=/studio/marking");
  await teacher.getByLabel("Email").fill("studio-reviewer@example.com");
  await teacher.getByLabel("Password").fill("studio-fixture-pass-1");
  await teacher.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(teacher).toHaveURL(/:\d+\/studio\/marking$/, AUTH);
  await teacher.getByRole("link", { name: `Script ${attemptId.slice(0, 8)}` }).click();
  await teacher.getByRole("button", { name: "Start marking" }).click();
  await teacher.getByLabel("Outcome for question 1").selectOption("pending");
  await teacher.getByLabel("Reason for question 1").fill("Fixture: part (b) is too faint to read.");
  await teacher.getByRole("button", { name: "Release result" }).click();
  await expect(teacher.getByText("Result released")).toBeVisible(AUTH);

  await page.reload();
  await expect(page.getByText("Marking isn't finished yet")).toBeVisible(AUTH);
  await expect(page.getByText(/Question 1: pending/)).toBeVisible();
  await expect(page.getByText("Fixture: part (b) is too faint to read.")).toBeVisible();

  await teacher.goto("/studio/marking");
  await teacher.getByRole("listitem").filter({ hasText: `Script ${attemptId.slice(0, 8)}` }).filter({ hasText: "Completion" }).getByRole("link").click();
  await expect(teacher.getByRole("region", { name: "Pending questions" })).toContainText("question: 1");
  await teacher.getByRole("button", { name: "Start marking" }).click();
  await teacher.getByRole("radiogroup", { name: "Award for a1" }).getByLabel("1", { exact: true }).check();
  await teacher.getByRole("button", { name: "Release result" }).click();
  await expect(teacher.getByText("Result released")).toBeVisible(AUTH);

  await page.reload();
  await expect(page.getByText(/marked by a teacher/)).toBeVisible(AUTH);
  await expect(page.getByText("Question 1: 1 / 5")).toBeVisible();
});

/** Save a marking draft, leave the case, and open it again (a real navigation, not client state). */
async function saveAndReopen(teacher: Page) {
  const caseUrl = teacher.url();
  const header = teacher.getByText(/· version \d+/);
  const before = await header.textContent();
  await teacher.getByRole("button", { name: "Save marks" }).click();
  await expect(header).not.toHaveText(before!, AUTH);
  await teacher.goto("/studio/marking");
  await teacher.goto(caseUrl);
}

test("a teacher asks for a clearer copy, the learner sends one, and it is classified before marking", async ({ page, browser }) => {
  test.slow(); // two marking rounds across two browser contexts
  await newLearner(page);
  await page.goto("/practice/written?grade=11&subject=biology");
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
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

  const teacher = await (await browser.newContext()).newPage();
  await teacher.goto("/signin?next=/studio/marking");
  await teacher.getByLabel("Email").fill("studio-reviewer@example.com");
  await teacher.getByLabel("Password").fill("studio-fixture-pass-1");
  await teacher.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(teacher).toHaveURL(/:\d+\/studio\/marking$/, AUTH);
  await teacher.getByRole("link", { name: `Script ${attemptId.slice(0, 8)}` }).click();
  await teacher.getByRole("button", { name: "Start marking" }).click();
  await teacher.getByLabel("Outcome for question 1").selectOption("pending");
  await teacher.getByLabel("Ask the learner about question 1").selectOption("rescan");
  await teacher.getByLabel("Reason for question 1").fill("Fixture: the photo is too dark to read.");
  // PR32-02: a saved draft reopens with its outcome, reason and learner action, not as "scored".
  await saveAndReopen(teacher);
  await expect(teacher.getByLabel("Outcome for question 1")).toHaveValue("pending");
  await expect(teacher.getByLabel("Ask the learner about question 1")).toHaveValue("rescan");
  await expect(teacher.getByLabel("Reason for question 1")).toHaveValue("Fixture: the photo is too dark to read.");
  await teacher.getByRole("button", { name: "Release result" }).click();
  await expect(teacher.getByText("Result released")).toBeVisible(AUTH);

  await page.reload();
  const action = page.getByRole("group", { name: "Action for question 1" });
  await expect(action).toContainText("couldn't read this answer", AUTH);
  await action.locator('input[type="file"]').setInputFiles("e2e/fixtures/synthetic-page-clearer.png");
  await expect(page.getByText(/Clearer copy sent .*waiting for a teacher/)).toBeVisible(AUTH);

  await teacher.goto("/studio/marking");
  await teacher.getByRole("listitem").filter({ hasText: `Script ${attemptId.slice(0, 8)}` }).filter({ hasText: "Completion" }).getByRole("link").click();
  await expect(teacher.getByAltText("Clearer copy 1 for question 1")).toBeVisible(AUTH);
  await expect(teacher.getByText(/before the upload deadline/)).toBeVisible(); // the authoritative timing, not a blanket label
  await teacher.getByRole("button", { name: "Start marking" }).click();
  await teacher.getByLabel("Classify the clearer copy for question 1").selectOption("READABILITY");
  await teacher.getByLabel("Reason for the classification of question 1").fill("Fixture: same working, brighter photo.");
  await teacher.getByLabel("Used the clearer copy for question 1 (recorded with the mark)").check();
  await teacher.getByRole("radiogroup", { name: "Award for a1" }).getByLabel("1", { exact: true }).check();
  // PR32-02: a draft may propose READABILITY and use that copy; the proposal and evidence choice survive a reload.
  await saveAndReopen(teacher);
  await expect(teacher.getByLabel("Classify the clearer copy for question 1")).toHaveValue("READABILITY");
  await expect(teacher.getByLabel("Reason for the classification of question 1")).toHaveValue("Fixture: same working, brighter photo.");
  await expect(teacher.getByLabel("Used the clearer copy for question 1 (recorded with the mark)")).toBeChecked();
  await expect(teacher.getByRole("radiogroup", { name: "Award for a1" }).getByLabel("1", { exact: true })).toBeChecked();
  await teacher.getByRole("button", { name: "Release result" }).click();
  await expect(teacher.getByText("Result released")).toBeVisible(AUTH);

  await page.reload();
  await expect(page.getByText("A teacher used your clearer copy to mark this answer.")).toBeVisible(AUTH);
  await expect(page.getByText("Question 1: 1 / 5")).toBeVisible();
});

test("uploads are refused from other sites", async ({ page }) => {
  await newLearner(page);
  const res = await page.request.post("/practice/written/00000000-0000-0000-0000-000000000000/upload", {
    data: "x",
    headers: { Origin: "https://evil.example" },
  });
  expect(res.status()).toBe(403);
});

test("a teacher marks a submitted script and the learner sees the released marks", async ({ page, browser }) => {
  await newLearner(page);
  await page.goto("/practice/written?grade=11&subject=biology");
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Start written test" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\/written\/[0-9a-f-]{36}$/, AUTH);
  const attemptId = page.url().split("/").pop()!;
  await page.getByLabel("Add photos or a PDF").setInputFiles("e2e/fixtures/synthetic-page.png");
  await expect(page.getByRole("list", { name: "Uploaded pages" }).getByText(/Page 1 ·/)).toBeVisible(AUTH);
  await page.getByRole("group", { name: /Question 1 \(a\)/ }).getByLabel("Page 1").check();
  await page.getByRole("group", { name: /Question 1 \(b\)/ }).getByLabel("I didn't answer this").check();
  await expect(page.getByRole("status").filter({ hasText: /Saved · revision \d+/ })).toBeVisible(AUTH);
  await page.getByRole("button", { name: "Submit for marking" }).click();
  await expect(page.getByText("Waiting for a teacher")).toBeVisible(AUTH);

  const teacher = await (await browser.newContext()).newPage();
  await teacher.goto("/signin?next=/studio/marking");
  await teacher.getByLabel("Email").fill("studio-reviewer@example.com");
  await teacher.getByLabel("Password").fill("studio-fixture-pass-1");
  await teacher.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(teacher).toHaveURL(/:\d+\/studio\/marking$/, AUTH);
  await teacher.getByRole("link", { name: `Script ${attemptId.slice(0, 8)}` }).click();
  await expect(teacher.getByAltText("Submitted page 1")).toBeVisible(AUTH);
  await expect(teacher.getByText("learner declared this part unanswered")).toBeVisible();
  // OCT8-06: a higher-detail rendition from the original, for small symbols and labels.
  const detailHref = await teacher.getByRole("link", { name: "Open in full detail" }).first().getAttribute("href");
  const detail = await teacher.request.get(detailHref!);
  expect(detail.status()).toBe(200);
  expect(detail.headers()["content-type"]).toBe("image/png");
  expect(detail.headers()["x-evidence-page"]).toBe("1");
  await teacher.getByRole("button", { name: "Start marking" }).click();
  await teacher.getByRole("radiogroup", { name: "Award for a1" }).getByLabel("1", { exact: true }).check();
  await teacher.getByLabel("Reason for a1").fill("Fixture reason: half the expected points.");
  await expect(teacher.getByText("Total 1 / 5")).toBeVisible();
  await teacher.getByRole("button", { name: "Release result" }).click();
  await expect(teacher.getByText("Result released")).toBeVisible(AUTH);

  await page.reload();
  await expect(page.getByText(/marked by a teacher/)).toBeVisible(AUTH);
  await expect(page.getByText("Question 1: 1 / 5")).toBeVisible();
  await expect(page.getByText("Fixture reason: half the expected points.")).toBeVisible();

  // A recheck is asked for once, inside the window, for named questions; it doesn't use more allowance.
  await page.getByText("Ask for a recheck").click();
  await page.getByRole("group", { name: "Which questions?" }).getByLabel("Question 1").check();
  await page.getByLabel("Why should it be marked again?").fill("Fixture reason: please look at part (a) again.");
  await page.getByRole("button", { name: "Request recheck" }).click();
  await expect(page.getByText("Recheck requested")).toBeVisible(AUTH);
  await expect(page.getByText("Ask for a recheck")).toHaveCount(0);

  // W04.S3.T3: answering again is a separate linked test. Preparing it charges nothing; the cost is shown before the
  // start, and the released marks above never change.
  await page.getByRole("button", { name: "Prepare a new practice test" }).click();
  await expect(page).toHaveURL(/\/practice\/written\/linked\/[0-9a-f-]{36}$/, AUTH);
  await expect(page.getByText("Your earlier result stays as it is")).toBeVisible();
  await expect(page.getByText(/\d+ units? \(you have \d+\)/)).toBeVisible();
  await page.getByRole("button", { name: "Start the new test" }).click();
  await expect(page.getByText("Linked to an earlier test")).toBeVisible(AUTH);
  expect(page.url()).not.toContain(attemptId);
  await page.goto(`/practice/written/${attemptId}`);
  await expect(page.getByText("Question 1: 1 / 5")).toBeVisible(AUTH);
  await expect(page.getByRole("link", { name: /^Questions 1/ })).toBeVisible();
  await teacher.goto("/studio/marking");
  const recheckRow = teacher.getByRole("listitem").filter({ hasText: `Script ${attemptId.slice(0, 8)}` }).filter({ hasText: "Recheck" });
  await expect(recheckRow).toBeVisible(AUTH);

  // The first marker can't recheck their own marking; a second teacher re-marks only the disputed question.
  await recheckRow.getByRole("link").click();
  await teacher.getByRole("button", { name: "Start marking" }).click();
  await expect(teacher.getByText(/not marked this script before/)).toBeVisible(AUTH);
  const second = await (await browser.newContext()).newPage();
  await second.goto("/signin?next=/studio/marking");
  await second.getByLabel("Email").fill("studio-reviewer2@example.com");
  await second.getByLabel("Password").fill("studio-fixture-pass-1");
  await second.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(second).toHaveURL(/:\d+\/studio\/marking$/, AUTH);
  await second.getByRole("listitem").filter({ hasText: `Script ${attemptId.slice(0, 8)}` }).filter({ hasText: "Recheck" }).getByRole("link").click();
  await expect(second.getByRole("region", { name: "Recheck request" })).toContainText("The learner disputes version 1: question 1");
  await expect(second.getByText("Fixture reason: please look at part (a) again.")).toBeVisible();
  await second.getByRole("button", { name: "Start marking" }).click();
  await second.getByRole("radiogroup", { name: "Award for a1" }).getByLabel("1", { exact: true }).check();
  await second.getByLabel("Reason for a1").fill("Fixture reason: upheld after recheck.");
  await second.getByRole("button", { name: "Release result" }).click();
  await expect(second.getByText("Result released")).toBeVisible(AUTH);

  await page.reload();
  await expect(page.getByText(/Version 2: 1 · after recheck/)).toBeVisible(AUTH);
  await expect(page.getByText(/already been rechecked/)).toBeVisible(); // upheld unchanged, so nothing new to appeal
});
