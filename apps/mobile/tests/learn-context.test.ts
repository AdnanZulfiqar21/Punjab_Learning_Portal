// Class 11 Biology Chapter 1 pilot: the Learn tab's class/group rules and the reader language rules, on the host.
// Not device evidence.
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { contextLine, parseStored, resolveContext } from "../src/lib/learn-context-core.ts";
import { comparisonCards } from "../src/lib/lesson-tables.ts";
import { missingLanguageNote, preferredLanguage } from "../src/lib/reading-language-core.ts";

describe("learn context", () => {
  it("needs both a class and a group; one alone is not a context", () => {
    assert.equal(resolveContext(null, { grade: 11 }).context, null);
    assert.equal(resolveContext(null, { stream: "pre_medical" }).context, null);
    assert.deepEqual(resolveContext(null, { grade: 11 }).partial, { grade: 11 });
  });

  it("uses the signed-in profile first and the device's choice for what it leaves open", () => {
    const fromProfile = resolveContext({ grade: 12, stream: "ics" }, { grade: 11, stream: "pre_medical" });
    assert.deepEqual(fromProfile.context, { grade: 12, stream: "ics" });
    assert.equal(fromProfile.source, "profile");
    const mixed = resolveContext({ grade: 11, stream: null }, { grade: 12, stream: "pre_engineering" });
    assert.deepEqual(mixed.context, { grade: 11, stream: "pre_engineering" }); // the profile's class, never the device's
    assert.equal(mixed.source, "device");
    const guest = resolveContext(null, { grade: 11, stream: "pre_medical" });
    assert.equal(guest.source, "device");
    assert.equal(contextLine(guest.context!), "Class 11 · Pre-Medical");
  });

  it("drops stored values it doesn't know", () => {
    assert.equal(parseStored({ grade: 10, stream: "commerce" }), null);
    assert.deepEqual(parseStored({ grade: 12, stream: "arts" }), { grade: 12 });
    assert.equal(parseStored("x"), null);
  });
});

describe("reader language", () => {
  it("prefers the device's choice, then the profile, then English", () => {
    assert.equal(preferredLanguage("roman_ur", "en"), "roman_ur");
    assert.equal(preferredLanguage(null, "roman_ur"), "roman_ur");
    assert.equal(preferredLanguage(null, "ur"), "en"); // Urdu script is not a reader choice yet
    assert.equal(preferredLanguage("fr", undefined), "en");
  });

  it("says honestly when the asked-for language is missing", () => {
    assert.equal(missingLanguageNote("roman_ur", "roman_ur", ["en", "roman_ur"]), null);
    assert.equal(missingLanguageNote("roman_ur", "en", ["en"]), "Roman Urdu isn’t available for this topic yet. Showing English.");
    assert.equal(missingLanguageNote("en", "roman_ur", ["roman_ur"]), "English isn’t available for this topic yet. Showing Roman Urdu.");
  });
});

describe("comparison tables", () => {
  it("turns each row into a card named by its first cell", () => {
    const cards = comparisonCards(
      ["Lipid", "Bacteria", "Archaea"],
      [
        ["Linkage", "Ester", "Ether"],
        ["Chains", "Unbranched fatty acids", "Branched isoprenoids"],
      ],
    );
    assert.deepEqual(cards, [
      { title: "Linkage", fields: [{ label: "Bacteria", value: "Ester" }, { label: "Archaea", value: "Ether" }] },
      { title: "Chains", fields: [{ label: "Bacteria", value: "Unbranched fatty acids" }, { label: "Archaea", value: "Branched isoprenoids" }] },
    ]);
  });

  it("leaves a one-column or empty table to the plain layout", () => {
    assert.equal(comparisonCards(["Only"], [["a"]]), null);
    assert.equal(comparisonCards(["A", "B"], []), null);
  });
});
