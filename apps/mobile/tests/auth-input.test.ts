// AUTH-PASSWORD-01 / AUTH-PREMIUM-01: host-side tests of src/lib/auth-input.ts; not device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { isoDate, looksLikeEmail, passwordStrength } from "../src/lib/auth-input.ts";

describe("isoDate", () => {
  it("reads day/month/year with any of / - . and pads", () => {
    assert.equal(isoDate("14/05/2008"), "2008-05-14");
    assert.equal(isoDate(" 4-5-2008 "), "2008-05-04");
    assert.equal(isoDate("04.05.2008"), "2008-05-04");
  });
  it("refuses dates that don't exist and other shapes", () => {
    assert.equal(isoDate("31/02/2008"), null);
    assert.equal(isoDate("2008-05-14"), null);
    assert.equal(isoDate("14/05/08"), null);
    assert.equal(isoDate(""), null);
  });
});

describe("passwordStrength", () => {
  it("is 0 when empty and grows with length and variety", () => {
    assert.equal(passwordStrength(""), 0);
    assert.equal(passwordStrength("abc"), 1);
    assert.equal(passwordStrength("abcdefghij"), 1);
    assert.equal(passwordStrength("abcdefghijklmn"), 2);
    assert.equal(passwordStrength("Abcdefghijklmn7"), 4);
  });
});

describe("looksLikeEmail", () => {
  it("catches obvious typos only", () => {
    assert.equal(looksLikeEmail("ali@example.com"), true);
    assert.equal(looksLikeEmail("ali@example"), false);
    assert.equal(looksLikeEmail("ali example.com"), false);
  });
});
