import type { ChapterSummary } from "@portal/contracts";

export const GRADE_LABEL: Record<number, string> = { 11: "Class XI", 12: "Class XII" };

export function parseGrade(raw: string): 11 | 12 | null {
  return raw === "11" ? 11 : raw === "12" ? 12 : null;
}

export function chapterHeading(label: string, ch: Pick<ChapterSummary, "number" | "contents_number">): string {
  return `${label} ${ch.number}`;
}

/** Ranges such as "PDF pages 4–35". Unknown values are shown as unknown, never guessed. */
export function pageRange(start?: number | null, end?: number | null): string {
  if (start == null && end == null) return "unknown";
  if (start === end) return `${start}`;
  return `${start ?? "?"}–${end ?? "?"}`;
}

const ASSESSMENT_LABELS: Record<string, string> = {
  MCQ: "MCQs",
  Short: "short questions",
  Constructed: "constructed-response",
  Long: "long questions",
  Numerical: "numericals",
  Exercise: "exercise questions",
  Conceptual: "inquisitive/conceptual",
  Project: "activities/projects",
  DiagramBased: "diagram-based",
  TableBased: "table-based",
};

export function assessmentSummary(counts: Record<string, number>): string[] {
  return Object.entries(counts)
    .filter(([, n]) => n > 0)
    .map(([k, n]) => `${n} ${ASSESSMENT_LABELS[k] ?? k}`);
}

export const CONTENT_STATE_TEXT: Record<string, { label: string; detail: string }> = {
  SOURCE_INDEXED: {
    label: "Textbook indexed",
    detail:
      "Chapter structure and page references come from the official textbook. Lessons, videos and practice tests appear here after academic review.",
  },
};
