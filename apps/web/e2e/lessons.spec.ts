import { expect, test, type Page } from "@playwright/test";

// Lesson access (review R07): premium lessons need a plan or the free trial; previews are open to everyone. Uses the two
// labelled fixture lessons from `portal-dev-seed-practice` (Class XI Biology, first chapter). Not academic content.
const AUTH = { timeout: 20_000 };
const PREVIEW = "Technical fixture preview lesson text.";
const PREMIUM = "Technical fixture premium lesson text.";

async function openFirstBiologyChapter(page: Page) {
  await page.goto("/learn");
  await page.getByRole("region", { name: "Class XI", exact: true }).getByRole("link", { name: /Biology/ }).click();
  await expect(page).toHaveURL(/\/learn\/11\/biology$/, AUTH);
  await page.getByRole("link", { name: /Chapter 1(?!\d)/ }).first().click();
  await expect(page.getByRole("region", { name: "Lessons" })).toBeVisible(AUTH);
  return page.getByRole("region", { name: "Lessons" });
}

test.skip(({ isMobile }) => isMobile && !process.env.E2E_FULL_MATRIX, "Lesson access journeys run on desktop");

test("anyone reads a free preview; a premium lesson shows what it is but not its text", async ({ page }) => {
  const lessons = await openFirstBiologyChapter(page);
  await expect(lessons.getByText(PREVIEW)).toBeVisible();
  await expect(lessons.getByText(/Free preview ·/).first()).toBeVisible(); // two fixture previews exist (P07.S1.T1)
  await expect(lessons.getByRole("heading", { name: "[FIXTURE] Premium lesson" })).toBeVisible();
  await expect(lessons.getByText("This lesson is included with a plan or the free 30-day trial.")).toBeVisible();
  await expect(lessons.getByText(PREMIUM)).toHaveCount(0);
});

test("a learner on the free trial reads premium lessons", async ({ page }) => {
  const email = `e2e-lessons-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  await page.goto("/signin?next=/account");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("lessons-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/(account|onboarding)/, AUTH);
  await page.goto("/account");
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);
  const lessons = await openFirstBiologyChapter(page);
  await expect(lessons.getByText(PREMIUM)).toBeVisible();
  await expect(lessons.getByText("This lesson is included with a plan")).toHaveCount(0);
});

// P07.S1.T1 (LESSON-BLOCKS-01): the labelled structured-blocks fixture lesson (free preview) from portal-dev-seed-practice.
test("structured blocks reach learners: worked example, diagram, formula rendering and handout", async ({ page, request }) => {
  const lessons = await openFirstBiologyChapter(page);
  const example = lessons.getByRole("region", { name: "Worked example: Technical fixture worked example" });
  await expect(example).toBeVisible();
  await expect(example.getByRole("listitem")).toHaveCount(2);
  const img = lessons.getByRole("img", { name: "A synthetic fixture image with a box and a label" });
  await img.scrollIntoViewIfNeeded();
  await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0), AUTH).toBe(true);
  // P01.S4.T2: the formula is typeset on the web, its text equivalent kept for screen readers only (EQUATION-TEXT-01);
  // its reviewed static rendering isn't needed.
  const formula = lessons.getByRole("article", { name: "[FIXTURE] Structured blocks lesson" }).locator('figure[data-typeset="ok"]');
  await expect(formula.locator(".katex")).toBeVisible(AUTH);
  await expect(formula.getByText("v equals u plus a t (fixture)")).toHaveClass(/sr-only/);
  await expect(formula).toHaveAccessibleName("v equals u plus a t (fixture)");
  await lessons.getByText("Describe this diagram").click();
  await expect(lessons.getByText("A grey box with the words 'Technical fixture diagram'.")).toBeVisible();
  // P11.S2.T1: the lesson's checkpoint is a self-check: nothing is sent or scored, the explanation appears on request.
  const checkpoint = lessons.getByRole("complementary", { name: "Check your understanding" });
  await expect(checkpoint.getByText("Technical fixture self-check prompt.")).toBeVisible();
  await checkpoint.getByRole("button", { name: "Show what a good answer contains" }).click();
  await expect(checkpoint.getByRole("status")).toHaveText("Fixture explanation shown when revealed.");
  // ...and each lesson but the last leads to the next one.
  const next = lessons.getByRole("link", { name: /^Next lesson: / }).first();
  const target = (await next.getAttribute("href"))!;
  await next.click();
  await expect(page).toHaveURL(new RegExp(`${target}$`));
  await expect(page.locator(target)).toBeInViewport();
  const handout = lessons.getByRole("link", { name: "Download: Technical fixture handout (PDF)" });
  const res = await request.get((await handout.getAttribute("href"))!);
  expect(res.status()).toBe(200);
  expect(res.headers()["content-type"]).toBe("application/pdf");
  expect(res.headers()["content-disposition"]).toContain("attachment");
});

// P01.S4.T2 (RENDERER-SPIKE-01): formulas and chemistry are typeset, a formula can't add a link or a class, one that can't
// be typeset shows its reviewed rendering, and an Urdu paragraph with English words reads right to left. Fixtures only.
test("notation: formulas and chemistry are typeset safely, and Urdu reads right to left", async ({ page }) => {
  const lessons = await openFirstBiologyChapter(page);
  const lesson = lessons.getByRole("article", { name: "[FIXTURE] Notation lesson" });
  await lesson.scrollIntoViewIfNeeded();
  const typeset = lesson.locator('figure[data-typeset="ok"]');
  await expect(typeset).toHaveCount(3, AUTH);
  const chemistry = typeset.filter({ hasText: "Fixture chemistry" });
  await expect(chemistry.locator(".katex-html")).toBeVisible();
  expect(await chemistry.locator("math msub").count()).toBeGreaterThan(0); // H₂, O₂ as real subscripts
  await expect(lesson.locator('a[href^="javascript:"], .fixture-injected')).toHaveCount(0);
  await expect(typeset.filter({ hasText: "must refuse" }).locator(".katex-html")).toContainText("\\href");

  const broken = lesson.locator('figure[data-typeset="failed"]');
  await expect(broken.getByRole("img", { name: "Fixture rendering: Fixture: a formula that cannot be typeset" })).toBeVisible();
  await expect(broken.getByText("couldn't be typeset here")).toBeVisible();

  const urdu = lesson.getByText(/^تکنیکی نمونہ/);
  await expect(urdu).toHaveAttribute("dir", "auto");
  expect(await urdu.evaluate((el) => getComputedStyle(el).direction)).toBe("rtl");
  expect(await lesson.getByText("Fixture formula: x equals a fraction").evaluate((el) => getComputedStyle(el).direction)).toBe("ltr");
});

// P11.S2.T2 (STUDY-TOOLS-01): a private note, a saved formula and a favourite topic, gathered on /study.
test("a learner keeps a private note, a saved formula and a favourite topic", async ({ page }) => {
  const email = `e2e-study-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  await page.goto("/signin?next=/account");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("study-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/(account|onboarding)/, AUTH);
  const lessons = await openFirstBiologyChapter(page);
  const lesson = lessons.getByRole("article", { name: "[FIXTURE] Structured blocks lesson" });

  await lesson.getByRole("button", { name: "Add a private note" }).click();
  await lesson.getByLabel("My private note").fill("Fixture note: check the units.");
  await lesson.getByRole("button", { name: "Save note" }).click();
  await expect(lesson.getByText("Saved. Only you can see this note.")).toBeVisible(AUTH);

  await lesson.getByRole("button", { name: "Save formula" }).first().click();
  await expect(lesson.getByRole("button", { name: "Saved to your formulas" }).first()).toBeVisible(AUTH);

  const star = page.getByRole("region", { name: "Topics" }).getByRole("button", { name: /^Add to favourites:/ }).first();
  const topic = (await star.getAttribute("aria-label"))!.replace("Add to favourites: ", "");
  await star.click();
  await expect(page.getByRole("button", { name: `Remove from favourites: ${topic}` })).toHaveAttribute("aria-pressed", "true", AUTH);

  await page.reload();
  await expect(page.getByRole("article", { name: "[FIXTURE] Structured blocks lesson" }).getByLabel("My private note")).toHaveValue(
    "Fixture note: check the units.",
    AUTH,
  );

  await page.goto("/study");
  await expect(page.getByRole("heading", { level: 1, name: "My study tools" })).toBeVisible(AUTH);
  await expect(page.getByRole("region", { name: "Notes" }).getByText("Fixture note: check the units.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Saved formulas" }).getByText("v = u + at")).toBeVisible();
  await expect(page.getByRole("region", { name: "Favourite topics" }).getByRole("link", { name: topic })).toBeVisible();
});
