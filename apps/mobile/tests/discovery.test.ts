// P13.S2.T1 (DISCOVERY-01): host tests of the filter query and the published-count sentence. Not device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { bookSummary, discoveryPath, filtersActive, type PublishedCounts } from "../src/lib/discovery.ts";

const empty: PublishedCounts = {
  state: "not_yet_published",
  live_lessons: 0,
  chapters_with_lessons: 0,
  chapter_label: "Chapter",
  preview_lessons: 0,
  practice_questions: 0,
};

describe("discovery filters", () => {
  it("sends no query until a known filter is chosen", () => {
    assert.equal(discoveryPath({}), "/v1/discovery");
    assert.equal(discoveryPath({ grade: "10", track: "commerce", subject: "statistics", exam: "?", availability: "all" }), "/v1/discovery");
    assert.equal(filtersActive({ availability: "all" }), false);
  });

  it("keeps class 11 and 12 as separate known values and drops anything else", () => {
    assert.equal(
      discoveryPath({ grade: "12", track: "ics", subject: "computer_science", exam: "mdcat", availability: "lessons" }),
      "/v1/discovery?grade=12&track=ics&subject=computer_science&exam=mdcat&availability=lessons",
    );
    assert.equal(discoveryPath({ grade: "11" }), "/v1/discovery?grade=11");
  });
});

describe("published counts", () => {
  it("says when nothing is published", () => {
    assert.equal(bookSummary(empty), "No reviewed lessons or practice questions published yet.");
  });

  it("counts lessons, previews and practice, and does not borrow a lesson count from practice", () => {
    assert.equal(
      bookSummary({ ...empty, state: "lessons", live_lessons: 1, chapters_with_lessons: 1, preview_lessons: 1, practice_questions: 2 }),
      "1 reviewed lesson in 1 chapter · 1 free preview · 2 practice questions",
    );
    assert.equal(
      bookSummary({ ...empty, state: "practice_only", practice_questions: 1, chapter_label: "Unit" }),
      "No reviewed lessons yet · 1 practice question",
    );
  });
});
