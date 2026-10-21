// READER-PLACE-01: returning to the same place when the reader switches between an English lesson that carries only
// the book and a Roman Urdu lesson with extra blocks (src/lib/variant-place.ts). Host-side tests; not device evidence.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { mapPlace, placeSignature, type PlaceBlock } from "../src/lib/variant-place.ts";

const sigs = (blocks: PlaceBlock[]) => blocks.map(placeSignature);

// Shaped like Biology XII 19.8: the book's text and box in English; the same plus our self-check and recap in Roman Urdu.
const english: PlaceBlock[] = [
  { type: "paragraph", text: "A mutation is a change in the content of the genetic message, from nucleotides to a whole chromosome." },
  { type: "list", ordered: false, items: ["Point mutations: change only one or a few nucleotides.", "Chromosomal mutations: changes in the structure or number of chromosomes."] },
  { type: "diagram", asset_version_id: "fig-mutation", alt: "Point and chromosomal mutations", caption: "Mutations" },
  { type: "callout", tone: "note", title: "For information", text: "Agents that cause mutations are mutagens; the organism is a mutant." },
];
const romanUrdu: PlaceBlock[] = [
  { type: "paragraph", text: "Mutation genetic paigham ke mawad mein tabdeeli hai: nucleotides se le kar poore chromosome tak." },
  { type: "list", ordered: false, items: ["Point mutations: sirf aik ya chand nucleotides badalte hain.", "Chromosomal mutations: chromosomes ki banawat ya tadaad mein tabdeeli."] },
  { type: "callout", tone: "tip", title: "Diagram ko samjhein", text: "Upar wali tasveer mein point mutation aik nucleotide badalti hai." },
  { type: "diagram", asset_version_id: "fig-mutation", alt: "Point aur chromosomal mutations", caption: "Mutations" },
  { type: "callout", tone: "note", title: "Maloomat", text: "Mutations paida karne wale awamil mutagens kehlate hain; jandar mutant kehlata hai." },
  { type: "checkpoint", mode: "self_check", prompt: "Mutagen aur mutant mein kya farq hai?", explanation: "Mutagen sabab hai; mutant woh jandar hai." },
  { type: "heading", level: 2, text: "Fauri khulasa" },
  { type: "list", ordered: false, items: ["Mutation: genetic paigham mein tabdeeli."] },
];

describe("language switch place", () => {
  it("maps each English block to its Roman Urdu partner, the figure to the same figure", () => {
    const from = sigs(english);
    const to = sigs(romanUrdu);
    assert.deepEqual([0, 1, 2, 3].map((i) => mapPlace(from, to, i)), [0, 1, 3, 4]);
  });

  it("a block only Roman Urdu has maps back to the nearest earlier English block", () => {
    const from = sigs(romanUrdu);
    const to = sigs(english);
    assert.equal(mapPlace(from, to, 2), 1); // our tip box: back to the list before it
    assert.equal(mapPlace(from, to, 3), 2); // the figure
    assert.equal(mapPlace(from, to, 5), 3); // our self-check: back to the book's box
    assert.equal(mapPlace(from, to, 7), 3); // our recap
  });

  it("identical structures map block for block", () => {
    const from = sigs(romanUrdu);
    assert.deepEqual(romanUrdu.map((_, i) => mapPlace(from, from, i)), romanUrdu.map((_, i) => i));
  });

  it("the book's questions listed in English find our self-checks in Roman Urdu", () => {
    const en: PlaceBlock[] = [
      { type: "paragraph", text: "Optical isomers rotate polarised light in opposite directions: dextrorotatory and laevorotatory." },
      { type: "heading", level: 2, text: "Quick check 18.7" },
      { type: "list", ordered: true, items: ["Which geometries show cis-trans isomerism?", "For [Ni(en)3]2+, state the coordination number."] },
    ];
    const ru: PlaceBlock[] = [
      { type: "paragraph", text: "Optical isomers polarised roshni ko ulti simton mein ghumate hain: dextrorotatory aur laevorotatory." },
      { type: "heading", level: 2, text: "Quick check 18.7" },
      { type: "checkpoint", mode: "self_check", prompt: "Kaun si geometries cis-trans isomerism dikhati hain?", explanation: "Square planar aur octahedral." },
      { type: "checkpoint", mode: "self_check", prompt: "[Ni(en)3]2+ ke liye coordination number batayein.", explanation: "6." },
      { type: "heading", level: 2, text: "Fauri khulasa" },
    ];
    assert.equal(mapPlace(sigs(en), sigs(ru), 2), 2);
    assert.equal(mapPlace(sigs(ru), sigs(en), 3), 2);
  });

  it("figures never pair with a different figure", () => {
    const a = [placeSignature({ type: "diagram", asset_version_id: "one" })];
    const b = [placeSignature({ type: "diagram", asset_version_id: "two" }), placeSignature({ type: "diagram", asset_version_id: "one" })];
    assert.equal(mapPlace(a, b, 0), 1);
    assert.equal(mapPlace(a, [], 0), 0);
  });

  it("is the same code on web and mobile", () => {
    const mobile = readFileSync(new URL("../src/lib/variant-place.ts", import.meta.url), "utf8");
    const web = readFileSync(new URL("../../web/src/lib/variant-place.ts", import.meta.url), "utf8");
    assert.equal(web, mobile);
  });
});
