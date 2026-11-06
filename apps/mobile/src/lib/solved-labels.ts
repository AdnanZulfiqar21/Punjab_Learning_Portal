// SOLVED-QUESTION-01: the words of a solved book question (Mathematics exercises), in each reading language. A plain
// module, so server and client components share the same values.
export type SolvedLabels = { question: string; think: string; step: string; answer: string; hide: string };

export const SOLVED_LABELS_EN: SolvedLabels = { question: "Question", think: "How to think about it", step: "Step", answer: "Final answer", hide: "Hide answer" };
export const SOLVED_LABELS_RU: SolvedLabels = { question: "Sawal", think: "Sochne ka tareeqa", step: "Qadam", answer: "Final jawab", hide: "Answer chhupayein" };

/** The words for a lesson language ("roman_ur" → Roman Urdu, else English). */
export function solvedLabels(language: string): SolvedLabels {
  return language === "roman_ur" ? SOLVED_LABELS_RU : SOLVED_LABELS_EN;
}

/** A numbered step's own text: the list draws the number, so a written "Step 2:" / "Qadam 2:" lead is dropped. */
export function stepText(step: string): string {
  return step.replace(/^\s*(?:step|qadam)\s*\d+\s*[:.)-]\s*/i, "");
}
