// DESIGN-01 (draft C · Soft Glass): the header marks the section the learner is in. Host-side tests of src/lib/nav.ts.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { activeSection, NAV_ITEMS } from "../src/lib/nav.ts";

describe("activeSection", () => {
  it("marks each main section on its own page and the pages below it", () => {
    assert.equal(activeSection("/learn"), "learn");
    assert.equal(activeSection("/learn/11/biology"), "learn");
    assert.equal(activeSection("/learn/topic/0b6c"), "learn");
    assert.equal(activeSection("/practice"), "practice");
    assert.equal(activeSection("/practice/attempt/42/result"), "practice");
    assert.equal(activeSection("/search"), "search");
    assert.equal(activeSection("/help"), "help");
    assert.equal(activeSection("/help/new"), "help");
  });

  it("treats the account's own pages as Account", () => {
    for (const p of ["/account", "/account/devices", "/signin", "/notifications", "/onboarding"]) {
      assert.equal(activeSection(p), "account", p);
    }
  });

  it("matches whole path segments only", () => {
    assert.equal(activeSection("/learning"), null);
    assert.equal(activeSection("/practiced"), null);
    assert.equal(activeSection("/helpful/x"), null);
  });

  it("ignores a trailing slash, a query and a fragment", () => {
    assert.equal(activeSection("/learn/"), "learn");
    assert.equal(activeSection("/search?q=cell"), "search");
    assert.equal(activeSection("/practice#top"), "practice");
  });

  it("marks nothing on the home page, other pages or an unknown path", () => {
    for (const p of ["/", "", "/pricing", "/studio", "/admin/service", "/study"]) assert.equal(activeSection(p), null, p);
    assert.equal(activeSection(null), null);
    assert.equal(activeSection(undefined), null);
  });
});

describe("NAV_ITEMS", () => {
  it("lists the header's sections in order, each linking to its own page", () => {
    assert.deepEqual(
      NAV_ITEMS.map((i) => [i.key, i.href, i.label]),
      [
        ["learn", "/learn", "Learn"],
        ["practice", "/practice", "Practice"],
        ["search", "/search", "Search"],
        ["help", "/help", "Help"],
      ],
    );
    for (const i of NAV_ITEMS) assert.equal(activeSection(i.href), i.key);
  });
});
