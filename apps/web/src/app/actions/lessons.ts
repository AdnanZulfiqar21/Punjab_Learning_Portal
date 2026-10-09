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
