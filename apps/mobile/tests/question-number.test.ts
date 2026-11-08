// QUESTION-NUMBER-01: a practice question's printed number is drawn apart from its words (src/lib/question-number.ts).
import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { splitQuestionNumber } from "../src/lib/question-number.ts";

describe("question number", () => {
  it("takes the printed number off the question's words", () => {
    assert.deepEqual(splitQuestionNumber("30 On a metre rule graduated in mm"), { number: "30", text: "On a metre rule graduated in mm" });
    assert.deepEqual(splitQuestionNumber("1. Which domain of life"), { number: "1", text: "Which domain of life" });
    assert.deepEqual(splitQuestionNumber("1 (ii) Simplify \\(i^{17}\\)."), { number: "1 (ii)", text: "Simplify \\(i^{17}\\)." });
    assert.deepEqual(splitQuestionNumber("6(a) Explain the role"), { number: "6(a)", text: "Explain the role" });
    assert.deepEqual(splitQuestionNumber("b) The size of dichromate ion"), { number: "b", text: "The size of dichromate ion" });
    assert.deepEqual(splitQuestionNumber("iii. Give reactions of methanol"), { number: "iii", text: "Give reactions of methanol" });
    assert.deepEqual(splitQuestionNumber("f. (i) Write the full electronic"), { number: "f. (i)", text: "Write the full electronic" });
  });

  it("leaves a question with no printed number alone", () => {
    assert.equal(splitQuestionNumber("A ball is thrown upwards."), null);
    assert.equal(splitQuestionNumber("1.5 g of carbon burns."), null);
    assert.equal(splitQuestionNumber("Is it a vector?"), null);
    assert.equal(splitQuestionNumber("30"), null);
  });
});
