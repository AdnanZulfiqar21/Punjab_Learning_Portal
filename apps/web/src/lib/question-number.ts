// QUESTION-NUMBER-01 (owner, 2026-11-08): on a Practice page a question's printed number ("30", "1 (ii)", "a)") is drawn
// apart from its words, so "30 On a metre rule" does not read as one sentence. Pure; shared by web and mobile.

const PART = String.raw`\s?\((?:[ivxl]{1,5}|[a-z])\)`;
const LEAD = new RegExp(String.raw`^(\d{1,3}[.)]?(?:${PART})?|\(?(?:[a-z]|[ivxl]{1,5})[.)](?:${PART})?)\s+(?=\S)`);

/** The number a practice question starts with, and its words; null when it starts with no number. */
export function splitQuestionNumber(prompt: string): { number: string; text: string } | null {
  const m = LEAD.exec(prompt);
  if (!m) return null;
  return { number: m[1].replace(/^\(?(\w+)[.)]$/, "$1"), text: prompt.slice(m[0].length) };
}
