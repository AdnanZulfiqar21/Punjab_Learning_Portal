// Learn context (Class XI Biology Chapter 1 pilot): which class and which study group the Learn tab shows. Pure rules,
// free of storage and React, so they run on the host in tests.
//
// Class and group are separate choices. Class XI Pre-Medical and Class XII Pre-Medical use different textbooks, and a
// group never implies a class. The subjects a group covers come from the API's discovery tracks (the `track` filter is
// what actually selects the books); the list here only labels the choice before the API has answered.

export type Grade = 11 | 12;
export type Stream = "pre_medical" | "pre_engineering" | "ics";
export type LearnContext = { grade: Grade; stream: Stream };

export const GRADES: readonly (readonly [Grade, string])[] = [
  [11, "Class XI"],
  [12, "Class XII"],
];

export const STREAMS: readonly (readonly [Stream, string, string])[] = [
  ["pre_medical", "Pre-Medical", "Biology, Chemistry, Physics"],
  ["pre_engineering", "Pre-Engineering", "Mathematics, Chemistry, Physics"],
  ["ics", "ICS", "Computer Science, Mathematics, Physics"],
];

export const STREAM_LABEL: Record<Stream, string> = { pre_medical: "Pre-Medical", pre_engineering: "Pre-Engineering", ics: "ICS" };
export const GRADE_LABEL: Record<Grade, string> = { 11: "Class XI", 12: "Class XII" };

export function isGrade(value: unknown): value is Grade {
  return value === 11 || value === 12;
}

export function isStream(value: unknown): value is Stream {
  return value === "pre_medical" || value === "pre_engineering" || value === "ics";
}

export type ProfileLike = { grade?: number | null; stream?: string | null } | null | undefined;

/**
 * The class and group to show. A signed-in learner's saved profile wins; a choice kept on this device fills what the
 * profile leaves open (a guest's choice, or a group the profile doesn't name). `source` says where the whole context
 * came from so the screen can say "from your profile" or offer to save it.
 */
export function resolveContext(
  profile: ProfileLike,
  device: Partial<LearnContext> | null,
): { context: LearnContext | null; partial: Partial<LearnContext>; source: "profile" | "device" | null } {
  const grade = isGrade(profile?.grade) ? profile.grade : isGrade(device?.grade) ? device.grade : undefined;
  const stream = isStream(profile?.stream) ? profile.stream : isStream(device?.stream) ? device.stream : undefined;
  const partial: Partial<LearnContext> = {};
  if (grade) partial.grade = grade;
  if (stream) partial.stream = stream;
  if (!grade || !stream) return { context: null, partial, source: null };
  const source = isGrade(profile?.grade) && isStream(profile?.stream) ? "profile" : "device";
  return { context: { grade, stream }, partial, source };
}

/** "Class XI · Pre-Medical" */
export function contextLine(ctx: LearnContext): string {
  return `${GRADE_LABEL[ctx.grade]} · ${STREAM_LABEL[ctx.stream]}`;
}

/** Whether a stored value is a usable device choice; anything hand-edited or from an older build is dropped. */
export function parseStored(raw: unknown): Partial<LearnContext> | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const out: Partial<LearnContext> = {};
  if (isGrade(r.grade)) out.grade = r.grade;
  if (isStream(r.stream)) out.stream = r.stream;
  return out.grade || out.stream ? out : null;
}
