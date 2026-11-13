// SEARCH-SUGGEST-01 (owner, 2026-11-13): what the search box suggests while the learner types, and how a suggestion's
// title marks the typed text. Pure; shared by the route that fetches them and the box that shows them.

/** One suggestion: a chapter or topic whose title matches. */
export type Suggestion = {
  kind: "chapter" | "topic";
  id: string;
  chapter_id: string;
  title: string;
  number: string | null;
  chapter_title: string;
  grade: number;
  subject_code: string;
  subject_name: string;
};

/** Where a suggestion opens: a topic itself, a chapter its chapter (as the search results do, SEARCH-TOPIC-LINK-01). */
export const suggestionHref = (s: Pick<Suggestion, "kind" | "id" | "chapter_id">) =>
  s.kind === "topic" ? `/learn/topic/${s.id}` : `/learn/chapter/${s.chapter_id}`;

/** The title in parts, the typed text (case-insensitive, first place it occurs) marked. */
export function markTyped(title: string, typed: string): { text: string; match: boolean }[] {
  const q = typed.trim();
  const at = q ? title.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (at < 0) return [{ text: title, match: false }];
  return [
    { text: title.slice(0, at), match: false },
    { text: title.slice(at, at + q.length), match: true },
    { text: title.slice(at + q.length), match: false },
  ].filter((p) => p.text);
}
