// Learn context on the web (Class 11 Biology Chapter 1 pilot): which class and study group the Learn page shows, and
// the reader language. Same rules as the app (apps/mobile/src/lib/learn-context-core.ts): class and group are separate
// choices, a signed-in learner's profile wins, and a guest's choice is kept in a small cookie with no personal data.

export type Grade = 11 | 12;
export type Stream = "pre_medical" | "pre_engineering" | "ics";
export type LearnContext = { grade: Grade; stream: Stream };
export type ReadingLanguage = "en" | "roman_ur";

export const LEARN_COOKIE = "portal-learn";
export const LANGUAGE_COOKIE = "portal-reading-language";
export const PREFS_MAX_AGE_S = 60 * 60 * 24 * 365;

export const GRADES: readonly (readonly [Grade, string])[] = [
  [11, "Class 11"],
  [12, "Class 12"],
];
export const STREAMS: readonly (readonly [Stream, string, string])[] = [
  ["pre_medical", "Pre-Medical", "Biology, Chemistry, Physics"],
  ["pre_engineering", "Pre-Engineering", "Mathematics, Chemistry, Physics"],
  ["ics", "ICS", "Computer Science, Mathematics, Physics"],
];
export const STREAM_SUBJECTS: Record<Stream, string[]> = {
  pre_medical: ["biology", "chemistry", "physics"],
  pre_engineering: ["mathematics", "chemistry", "physics"],
  ics: ["computer_science", "mathematics", "physics"],
};
export const GRADE_LABEL: Record<Grade, string> = { 11: "Class 11", 12: "Class 12" };
export const STREAM_LABEL: Record<Stream, string> = { pre_medical: "Pre-Medical", pre_engineering: "Pre-Engineering", ics: "ICS" };
export const READING_LANGUAGES: readonly (readonly [ReadingLanguage, string])[] = [
  ["en", "English"],
  ["roman_ur", "Roman Urdu"],
];

export const isGrade = (v: unknown): v is Grade => v === 11 || v === 12;
export const isStream = (v: unknown): v is Stream => v === "pre_medical" || v === "pre_engineering" || v === "ics";
export const isReadingLanguage = (v: unknown): v is ReadingLanguage => v === "en" || v === "roman_ur";

/** "11.pre_medical" → the device's choice; anything else is ignored. */
export function parseLearnCookie(raw: string | null | undefined): Partial<LearnContext> {
  const [g, s] = (raw ?? "").split(".");
  const out: Partial<LearnContext> = {};
  const grade = Number(g);
  if (isGrade(grade)) out.grade = grade;
  if (isStream(s)) out.stream = s;
  return out;
}

export function serializeLearnContext(ctx: LearnContext): string {
  return `${ctx.grade}.${ctx.stream}`;
}

type ProfileLike = { grade?: number | null; stream?: string | null } | null | undefined;

/** The profile first, then the device's choice for what the profile leaves open; whole only with both parts. */
export function resolveContext(
  profile: ProfileLike,
  device: Partial<LearnContext>,
): { context: LearnContext | null; partial: Partial<LearnContext>; source: "profile" | "device" | null } {
  const grade = isGrade(profile?.grade) ? profile.grade : device.grade;
  const stream = isStream(profile?.stream) ? profile.stream : device.stream;
  const partial: Partial<LearnContext> = {};
  if (grade) partial.grade = grade;
  if (stream) partial.stream = stream;
  if (!grade || !stream) return { context: null, partial, source: null };
  return { context: { grade, stream }, partial, source: isGrade(profile?.grade) && isStream(profile?.stream) ? "profile" : "device" };
}

/** The language to read in: the device's choice, else the profile's explanation language, else English. */
export function preferredLanguage(device: string | null | undefined, profileLanguage: string | null | undefined): ReadingLanguage {
  if (isReadingLanguage(device)) return device;
  if (isReadingLanguage(profileLanguage)) return profileLanguage;
  return "en";
}

export const LANGUAGE_NAME: Record<string, string> = { en: "English", ur: "Urdu", roman_ur: "Roman Urdu" };

/** What to say when the lesson came back in another language than asked for. */
export function missingLanguageNote(requested: ReadingLanguage, shown: string): string | null {
  if (requested === shown) return null;
  return `${LANGUAGE_NAME[requested]} isn’t available for this topic yet. Showing ${LANGUAGE_NAME[shown] ?? shown}.`;
}

/** Subject accent (globals.css `[data-subject]`): the API's subject name or code → the CSS key. */
export function subjectKey(nameOrCode: string | null | undefined): string | undefined {
  const key = (nameOrCode ?? "").trim().toLowerCase().replace(/\s+/g, "_");
  return ["biology", "chemistry", "physics", "mathematics", "computer_science"].includes(key) ? key : undefined;
}
