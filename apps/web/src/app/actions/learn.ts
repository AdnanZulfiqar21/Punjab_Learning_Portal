"use server";

// Class XI Biology Chapter 1 pilot: the Learn page's class and group, and the reader language. Both are remembered on
// this device in small cookies (no personal data) and, for a signed-in learner, in the profile through the existing
// profile service. A guest's choice never creates an account or a server-side record.
import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { ProfileInput } from "@portal/contracts";
import {
  isGrade,
  isReadingLanguage,
  isStream,
  LANGUAGE_COOKIE,
  LEARN_COOKIE,
  PREFS_MAX_AGE_S,
  serializeLearnContext,
  STREAM_SUBJECTS,
  type LearnContext,
  type ReadingLanguage,
} from "@/lib/learn-context";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { api, currentUser } from "@/lib/session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function cookieOptions() {
  const { role } = readRuntimeConfig();
  return { httpOnly: true, sameSite: "lax" as const, secure: role === "staging" || role === "production", path: "/", maxAge: PREFS_MAX_AGE_S };
}

/** The signed-in learner's profile with these changes, or null when there is no one to save it for. */
async function profilePatch(patch: Partial<Pick<ProfileInput, "grade" | "stream" | "subjects" | "explanation_language">>): Promise<void> {
  const user = await currentUser();
  if (!user) return;
  const p = user.me.profile;
  const grade = patch.grade ?? p?.grade ?? null;
  if (!grade) return; // the profile service needs a class; a language alone is kept on the device until there is one
  const body: ProfileInput = {
    grade,
    stream: patch.stream ?? p?.stream ?? null,
    subjects: patch.subjects ?? p?.subjects ?? [],
    target_exams: p?.target_exams ?? [],
    target_year: p?.target_year ?? null,
    explanation_language: patch.explanation_language ?? p?.explanation_language ?? "en",
    daily_minutes: p?.daily_minutes ?? null,
  };
  await api("/v1/me/profile", { method: "PUT", token: user.token, body: JSON.stringify(body) }); // best effort: the cookie already applies
}

export async function chooseLearnContext(form: FormData): Promise<void> {
  const grade = Number(form.get("grade"));
  const stream = form.get("stream");
  if (!isGrade(grade) || !isStream(stream)) redirect(`/learn?change=1${isGrade(grade) ? `&grade=${grade}` : ""}${isStream(stream) ? `&track=${stream}` : ""}`);
  const ctx: LearnContext = { grade, stream };
  (await cookies()).set(LEARN_COOKIE, serializeLearnContext(ctx), cookieOptions());
  await profilePatch({ grade, stream, subjects: STREAM_SUBJECTS[stream] as ProfileInput["subjects"] });
  revalidatePath("/learn"); // the router keeps the page it rendered before the choice; show the chosen class and group
  redirect("/learn");
}

export async function chooseReadingLanguage(form: FormData): Promise<void> {
  const topicId = String(form.get("topic") ?? "");
  const language = form.get("language");
  const back = UUID.test(topicId) ? `/learn/topic/${topicId}` : "/learn";
  if (!isReadingLanguage(language)) redirect(back);
  const lang: ReadingLanguage = language;
  (await cookies()).set(LANGUAGE_COOKIE, lang, cookieOptions());
  await profilePatch({ explanation_language: lang });
  revalidatePath(back); // the reader re-renders in the chosen language rather than from the router's copy
  redirect(back);
}
