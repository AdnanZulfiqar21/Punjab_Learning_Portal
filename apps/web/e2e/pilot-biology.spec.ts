import { expect, test, type Page } from "@playwright/test";
import { audit } from "./helpers/a11y";

// Class XI Biology Chapter 1 pilot: choose class then group on Learn; a topic page that is honest when nothing is
// published; and, for staff who cover the subject, the draft read in English and Roman Urdu at the same place.
// The chapter and topic IDs are stable catalogue IDs. The pilot drafts come from content/tools/import_lessons.py
// (CI runs it after the development seed); they are private drafts, never published by these tests.
const AUTH = { timeout: 20_000 };
const CHAPTER = "/learn/chapter/317f2726-31a1-55f5-bd13-a955154033e2";
const TOPIC_1_1 = "/learn/topic/255b5a9d-355f-56ca-adb6-10fc6d2825fb";
const TOPIC_1_4 = "/learn/topic/76f9dd82-42bb-53e0-870a-c80135498adc";

async function signInStaff(page: Page, email: string) {
  await page.goto("/signin?next=/learn");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("studio-fixture-pass-1");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/learn$/, AUTH);
}

test("a guest chooses a class and a study group and sees only that class's books for it", async ({ page }) => {
  await page.goto("/learn");
  const chooser = page.getByRole("form", { name: "What are you studying?" });
  await expect(chooser.getByRole("radio", { name: "Class XI", exact: true })).toBeVisible();
  // Every book is still listed, Class XI and XII apart, until a class and group are chosen.
  await expect(page.getByRole("region", { name: "Class XI", exact: true })).toBeVisible();
  await chooser.getByRole("radio", { name: "Class XI", exact: true }).check();
  await chooser.getByRole("radio", { name: "Pre-Medical" }).check();
  await chooser.getByRole("button", { name: "Show my subjects" }).click();

  await expect(page.getByText("Class XI · Pre-Medical")).toBeVisible(AUTH);
  const subjects = page.getByRole("region", { name: "Your subjects" });
  for (const name of ["Biology", "Chemistry", "Physics"]) await expect(subjects.getByRole("link", { name: new RegExp(`^${name}`) })).toBeVisible();
  await expect(subjects.getByRole("link", { name: /Computer Science/ })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Class XII", exact: true })).toHaveCount(0);
  await expect(page.getByText("Chosen on this device")).toBeVisible();

  // The choice is kept on this device, and can be changed.
  await page.goto("/learn");
  await expect(page.getByText("Class XI · Pre-Medical")).toBeVisible();
  await page.getByRole("link", { name: "Change class or study group" }).click();
  await expect(page.getByRole("form", { name: "What are you studying?" })).toBeVisible();
  await expect(page.getByRole("radio", { name: "Pre-Medical" })).toBeChecked();
  await audit(page, null);
});

test("the chapter page leads with its topics and keeps the published lessons below", async ({ page }) => {
  await page.goto(CHAPTER);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Biodiversity");
  const topics = page.getByRole("region", { name: "Topics" });
  await expect(topics.getByRole("link", { name: /^1\.1 / })).toBeVisible();
  const headings = page.locator("main h2");
  await expect(headings.first()).toHaveText("Topics");
  await expect(page.getByRole("region", { name: "Lessons" })).toBeVisible();
  // No internal identifiers for learners: the textbook panel keeps book pages, not source references.
  await expect(page.getByText(/Source reference/)).toHaveCount(0);
  await audit(page, null);
});

test("a topic without a published lesson says so and offers no language choice", async ({ page }) => {
  await page.goto(TOPIC_1_1);
  await expect(page.getByRole("heading", { level: 1, name: /^1\.1 / })).toBeVisible();
  await expect(page.getByText("This topic’s lesson isn’t ready yet")).toBeVisible();
  await expect(page.getByRole("group", { name: "Read or watch" })).toHaveCount(0);
  await expect(page.getByText("Draft preview")).toHaveCount(0);
  await audit(page, null);
});

test("staff who cover the subject read the draft in English, then in Roman Urdu at the same place", async ({ page, isMobile }) => {
  test.skip(isMobile && !process.env.E2E_FULL_MATRIX, "The staff preview journey runs on desktop");
  await signInStaff(page, "studio-author@example.com");
  await page.goto(TOPIC_1_4);
  await expect(page.getByRole("heading", { level: 1, name: /^1\.4 / })).toBeVisible();
  await expect(page.getByText("Draft preview", { exact: true })).toBeVisible();
  const languages = page.getByRole("group", { name: "Read or watch" });
  // The staff fixture account may have saved Roman Urdu on an earlier run; start from English, and let the page
  // settle after the switch (the action re-renders the lesson, which would reset the turntable below).
  const english = languages.getByRole("button", { name: "English" });
  await page.waitForLoadState("networkidle");
  if ((await english.getAttribute("aria-pressed")) !== "true") {
    await english.click();
    await expect(english).toHaveAttribute("aria-pressed", "true", AUTH);
    await page.waitForLoadState("networkidle");
  }
  // Renderer 2: a comparison table folds into cards on narrow screens; a model shows its poster, then a turntable.
  const model = page.locator("figure").filter({ hasText: "3D model" }).first();
  await model.scrollIntoViewIfNeeded();
  const poster = model.getByRole("img").first();
  await expect.poll(() => poster.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0), AUTH).toBe(true);
  await model.getByRole("button", { name: "Rotate the model" }).click();
  const turntable = model.getByRole("slider");
  await expect(turntable).toHaveAttribute("aria-valuenow", "1");
  await turntable.focus();
  await page.keyboard.press("ArrowRight");
  await expect(turntable).toHaveAttribute("aria-valuenow", "2");

  // Switch to Roman Urdu from a block further down: the page returns to that block in the other variant.
  const anchor = page.locator("[data-block]").nth(6);
  await anchor.evaluate((el) => el.scrollIntoView({ block: "start" }));
  await languages.getByRole("button", { name: "Roman Urdu" }).click();
  await expect(languages.getByRole("button", { name: "Roman Urdu" })).toHaveAttribute("aria-pressed", "true", AUTH);
  await expect(page.getByText(/Roman Urdu isn’t available/)).toHaveCount(0);
  await expect(page.locator("[data-block]").nth(6)).toBeInViewport(AUTH);
  await expect(page.locator("[data-block]").nth(0)).not.toBeInViewport();
  // The preference is kept: another topic opens in Roman Urdu too.
  await page.goto(TOPIC_1_1);
  await expect(page.getByRole("group", { name: "Read or watch" }).getByRole("button", { name: "Roman Urdu" })).toHaveAttribute("aria-pressed", "true");
  // Lecture: the third choice. No approved lecture is registered for this topic, so it says so and keeps the text.
  await page.getByRole("group", { name: "Read or watch" }).getByRole("link", { name: "Lecture" }).click();
  await expect(page).toHaveURL(/\?view=lecture$/);
  // CI has no lecture registered (coming); a development database with registered masters shows the player instead.
  const lecture = page.getByRole("region", { name: "Lecture" });
  await expect(lecture.getByText("The lecture for this topic is coming").or(lecture.locator("video"))).toBeVisible(AUTH);
  await expect(page.locator("[data-block]").first()).toBeVisible();
  await page.getByRole("group", { name: "Read or watch" }).getByRole("link", { name: "Roman Urdu" }).click();
  await expect(page).not.toHaveURL(/view=lecture/);
  await audit(page, null);
});
