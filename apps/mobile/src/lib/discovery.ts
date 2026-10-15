// P11.S1.T3 / P13.S2.T1 (DISCOVERY-01): the same published-book filters the web Learn page sends.
// Unknown values are dropped, so a hand-edited filter never becomes an API error.

export const SUBJECTS = [
  ["biology", "Biology"],
  ["chemistry", "Chemistry"],
  ["physics", "Physics"],
  ["computer_science", "Computer Science"],
  ["mathematics", "Mathematics"],
] as const;

export const AVAILABILITY = [
  ["all", "Everything"],
  ["lessons", "Has reviewed lessons"],
  ["previews", "Has free previews"],
  ["practice", "Has practice questions"],
] as const;

const TRACKS = new Set(["pre_medical", "pre_engineering", "ics"]);
const SUBJECT_CODES = new Set<string>(SUBJECTS.map(([code]) => code));

export type DiscoveryFilters = {
  grade?: string;
  track?: string;
  subject?: string;
  exam?: string;
  availability?: string;
};

export type PublishedCounts = {
  state: "lessons" | "practice_only" | "not_yet_published";
  live_lessons: number;
  chapters_with_lessons: number;
  chapter_label: string;
  preview_lessons: number;
  practice_questions: number;
};

export function discoveryPath(filters: DiscoveryFilters): string {
  const q = new URLSearchParams();
  if (filters.grade === "11" || filters.grade === "12") q.set("grade", filters.grade);
  if (filters.track && TRACKS.has(filters.track)) q.set("track", filters.track);
  if (filters.subject && SUBJECT_CODES.has(filters.subject)) q.set("subject", filters.subject);
  if (filters.exam && /^[A-Za-z0-9_-]{2,40}$/.test(filters.exam)) q.set("exam", filters.exam);
  if (filters.availability === "lessons" || filters.availability === "previews" || filters.availability === "practice") {
    q.set("availability", filters.availability);
  }
  const query = q.toString();
  return `/v1/discovery${query ? `?${query}` : ""}`;
}

export function filtersActive(filters: DiscoveryFilters): boolean {
  return discoveryPath(filters) !== "/v1/discovery";
}

/** What is actually published for one book. A book with nothing published says so. */
export function bookSummary(book: PublishedCounts): string {
  if (book.state === "not_yet_published") return "No reviewed lessons or practice questions published yet.";
  const parts: string[] = [];
  if (book.live_lessons) {
    const chapters = book.chapters_with_lessons === 1 ? "" : "s";
    const lessons = book.live_lessons === 1 ? "" : "s";
    parts.push(
      `${book.live_lessons} reviewed lesson${lessons} in ${book.chapters_with_lessons} ${book.chapter_label.toLowerCase()}${chapters}`,
    );
  } else {
    parts.push("No reviewed lessons yet");
  }
  if (book.preview_lessons) parts.push(`${book.preview_lessons} free preview${book.preview_lessons === 1 ? "" : "s"}`);
  if (book.practice_questions) {
    parts.push(`${book.practice_questions} practice question${book.practice_questions === 1 ? "" : "s"}`);
  }
  return parts.join(" · ");
}
