"use server";

// P07.S1.T3 (LESSON-DONE-01): mark a lesson you can read as completed, or undo it.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { api, sessionToken } from "@/lib/session";

export async function setLessonCompleted(lessonId: string, chapterId: string, done: boolean): Promise<void> {
  const path = `/learn/chapter/${encodeURIComponent(chapterId)}`;
  const t = await sessionToken();
  if (!t) redirect(`/signin?next=${encodeURIComponent(path)}`);
  await api<null>(`/v1/me/lessons/${encodeURIComponent(lessonId)}/complete`, { method: done ? "POST" : "DELETE", token: t });
  revalidatePath(path);
}

/** P16.S2.T1: the lesson.started analytics event (the API records it at most once per lesson per day). */
export async function recordLessonStart(lessonId: string, language: string): Promise<void> {
  const t = await sessionToken();
  if (!t) return;
  await api<null>("/v1/me/events/lesson-started", { method: "POST", token: t, body: JSON.stringify({ lesson_id: lessonId, language }) });
}
